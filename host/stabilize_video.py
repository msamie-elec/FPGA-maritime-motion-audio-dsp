"""Run software-reference or REAL FPGA motion smoothing for synthetic video.

Always preserve honest mode/provenance in metrics and on-screen labels.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import numpy as np
import cv2
from fixed_point_golden import centered_smooth
from fpga_serial_client import run_two_axes
from processing_control import checkpoint, progress as notify
from generate_synthetic_clip import generate
from audio_preservation import mux_original_audio


def inputs_from_csv(path:Path):
    with path.open(newline='') as f: rows=list(csv.DictReader(f))
    return [int(r['x_q16_8']) for r in rows],[int(r['y_q16_8']) for r in rows]


def smooth_trajectory(samples: list[int], port: str | None = None, axis_id: int = 1, *,
                      cancel_event=None, progress=None):
    """Centred FIR, with correct 8-sample overlap for multi-packet FPGA jobs.

    At most 496 *new* trajectory samples fit in each 512-word UART job,
    leaving 8 samples of actual left context and 8 of right context.
    Each FPGA packet resets its FIR state, but overlap preserves the
    exact continuous FIR output at EVERY internal segment boundary.
    """
    if not samples:
        return []
    checkpoint(cancel_event)
    if port is None:
        v = centered_smooth(samples)
        notify(progress, "motion_fir", len(samples), len(samples))
        return v
    from fpga_serial_client import run_batch
    block_size = 512 - 16
    expected_all = centered_smooth(samples)
    actual = []
    for start in range(0, len(samples), block_size):
        checkpoint(cancel_event)  # do not interrupt a UART packet
        segment = samples[start:start + block_size]
        # Use global source history where available, replicate only real video edges.
        left = [samples[max(0, i)] for i in range(start - 8, start)]
        right = [samples[min(len(samples) - 1, i)] for i in range(start + len(segment), start + len(segment) + 8)]
        padded = left + segment + right
        assert 17 <= len(padded) <= 512
        returned = run_batch(port, padded, axis_id)
        if len(returned) != len(padded):
            raise AssertionError("FPGA did not return full overlapping batch")
        # With first valid target sample at padded index 8, causal output
        # at sequence index 16 corresponds to that centred target.
        block_out = returned[16:16 + len(segment)]
        expected_block = expected_all[start:start + len(segment)]
        if block_out != expected_block:
            raise AssertionError(
                f"FPGA FIR mismatch in job {axis_id}, frames {start}..{start+len(segment)-1}; "
                "no hardware-verified result permitted"
            )
        actual.extend(block_out)
        notify(progress, "motion_fir", len(actual), len(samples))
    checkpoint(cancel_event)
    assert actual == expected_all
    return actual


def rms(v): return float(np.sqrt(np.mean(np.square(v))))


def evaluate(original,filtered,frame_rate:int=30):
    # HF residual relative to a 1-second centred moving average; diagnostic only.
    n=len(original);k=31
    def hf(a): return a-np.convolve(np.pad(a,(k//2,k//2),mode='edge'),np.ones(k)/k,mode='valid')
    orig=np.array(original,dtype=float)/256
    filt=np.array(filtered,dtype=float)/256
    return {'raw_high_frequency_rms_px':rms(hf(orig)),
        'filtered_high_frequency_rms_px':rms(hf(filt)),
        'reduction_pct':float(100*(1-rms(hf(filt))/max(1e-12,rms(hf(orig)))))}


def stabilize(video_path:Path,trajectory_path:Path,output_dir:Path,port:str|None=None, *, cancel_event=None, progress=None):
    output_dir.mkdir(parents=True,exist_ok=True)
    x,y=inputs_from_csv(trajectory_path)
    fx=smooth_trajectory(x,port,1,cancel_event=cancel_event)
    checkpoint(cancel_event)
    notify(progress, 'motion_fir', 1, 2)
    fy=smooth_trajectory(y,port,2,cancel_event=cancel_event)
    notify(progress, 'motion_fir', 2, 2)
    mode='PHYSICAL FPGA - BIT-EXACT VERIFIED' if port else 'SOFTWARE REFERENCE ONLY'
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise RuntimeError('Cannot open input video')
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=cap.get(cv2.CAP_PROP_FPS) or 30
    outpath=output_dir/('fpga_before_after.mp4' if port else 'software_preview_before_after.mp4')
    writer=cv2.VideoWriter(str(outpath),cv2.VideoWriter_fourcc(*'mp4v'),fps,(2*width,height))
    if not writer.isOpened():raise RuntimeError('Cannot write MP4')
    count=0
    try:
      while True:
        checkpoint(cancel_event)
        if count == 0 or count % 12 == 0:
            notify(progress,'video_render',count,len(x))
        ok,frame=cap.read()
        if not ok:break
        if count>=len(x):raise RuntimeError('input video has extra frames')
        # Input frame has transform +x,+y. Correct with target-original.
        dx=(fx[count]-x[count])/256.0;dy=(fy[count]-y[count])/256.0
        corrected=cv2.warpAffine(frame,np.float32([[1,0,dx],[0,1,dy]]),(width,height),borderMode=cv2.BORDER_REFLECT_101)
        pair=np.hstack([frame,corrected])
        for offset,label in [(0,'ORIGINAL - INPUT'),(width,'STABILISED - '+mode)]:
            cv2.rectangle(pair,(offset,0),(offset+width,28),(18,36,53),-1)
            cv2.putText(pair,label,(offset+12,20),cv2.FONT_HERSHEY_SIMPLEX,0.48,(245,245,245),1,cv2.LINE_AA)
        writer.write(pair);count+=1
    finally:
      cap.release();writer.release()
    checkpoint(cancel_event)
    notify(progress,'video_render',count,len(x))
    if count!=len(x):raise RuntimeError(f'frame mismatch: video={count}, trajectory={len(x)}')
    audio_info = mux_original_audio(outpath, video_path,cancel_event=cancel_event)
    metrics={'mode':mode,'frames':count,'source_video':video_path.name,'physical_port':port,'audio':audio_info,
             'x':evaluate(x,fx),'y':evaluate(y,fy),'pass_target_30pct':False}
    metrics['pass_target_30pct']=(metrics['x']['reduction_pct']>=30 and metrics['y']['reduction_pct']>=30)
    (output_dir/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    (output_dir/'filtered_trajectory.json').write_text(json.dumps({'mode':mode,'x':fx,'y':fy},indent=2)+'\n')
    return outpath,metrics


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--video',type=Path)
    a.add_argument('--trajectory',type=Path)
    a.add_argument('--out',type=Path,default=Path('build/maritime_demo'))
    a.add_argument('--port',help='Physical FPGA UART, e.g. COM6. Omit for labelled software-only preview.')
    z=a.parse_args();z.out.mkdir(parents=True,exist_ok=True)
    if z.video is None or z.trajectory is None:
        video,traj=generate(z.out)
    else:video,traj=z.video,z.trajectory
    path,metrics=stabilize(video,traj,z.out,z.port)
    print('Created:',path,'\nMetrics:',json.dumps(metrics,indent=2))
if __name__=='__main__':main()

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
from generate_synthetic_clip import generate


def inputs_from_csv(path:Path):
    with path.open(newline='') as f: rows=list(csv.DictReader(f))
    return [int(r['x_q16_8']) for r in rows],[int(r['y_q16_8']) for r in rows]


def smooth_trajectory(samples: list[int], port: str|None = None, axis_id:int=1):
    # 8 replicate pads at each edge. Filter starts with ZERO history per axis.
    padded=[samples[0]]*8+samples+[samples[-1]]*8
    if len(padded)>512:
        raise ValueError('This demonstration supports at most 496 frames, including pads')
    if port:
        from fpga_serial_client import run_batch
        raw=run_batch(port,padded,axis_id)
        golden=centered_smooth(samples)
        values=raw[16:16+len(samples)]
        if values!=golden:
            raise AssertionError('FPGA and bit-exact golden differ; refusing hardware-validated video')
        return values
    return centered_smooth(samples)


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


def stabilize(video_path:Path,trajectory_path:Path,output_dir:Path,port:str|None=None):
    output_dir.mkdir(parents=True,exist_ok=True)
    x,y=inputs_from_csv(trajectory_path)
    fx=smooth_trajectory(x,port,1)
    fy=smooth_trajectory(y,port,2)
    mode='PHYSICAL FPGA - BIT-EXACT VERIFIED' if port else 'SOFTWARE REFERENCE ONLY'
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise RuntimeError('Cannot open input video')
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=cap.get(cv2.CAP_PROP_FPS) or 30
    outpath=output_dir/('fpga_before_after.mp4' if port else 'software_preview_before_after.mp4')
    writer=cv2.VideoWriter(str(outpath),cv2.VideoWriter_fourcc(*'mp4v'),fps,(2*width,height))
    if not writer.isOpened():raise RuntimeError('Cannot write MP4')
    count=0
    while True:
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
    cap.release();writer.release()
    if count!=len(x):raise RuntimeError(f'frame mismatch: video={count}, trajectory={len(x)}')
    metrics={'mode':mode,'frames':count,'source_video':video_path.name,'physical_port':port,
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

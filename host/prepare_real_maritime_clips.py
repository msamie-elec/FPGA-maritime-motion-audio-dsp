"""Prepare two attributed REAL stock-footage source files for the FPGA GUI.

The source videos must be supplied by the user from their respective Pexels pages.
We do not create, infer or label synthetic footage as original camera footage.
The output 'shaky' examples contain genuine video frames PLUS INJECTED CAMERA
TRANSLATION for deterministic, FPGA-verifiable motion filtering.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import hashlib
from pathlib import Path

import cv2
import numpy as np

SOURCES = {
    'ferry': {
        'title': 'Silhouettes on Ferry with Cargo Ship View',
        'creator': 'Rahime Gül',
        'url': 'https://www.pexels.com/video/silhouettes-on-ferry-with-cargo-ship-view-28945771/',
        'source_id': '28945771',
        'source_orientation': 'portrait',
        'label': 'Ferry view of a cargo ship',
    },
    'pilot': {
        'title': 'A Boat Sailing alongside a Cargo Ship',
        'creator': 'Alexander Grigorian',
        'url': 'https://www.pexels.com/video/a-boat-sailing-alongside-a-cargo-ship-7397246/',
        'source_id': '7397246',
        'source_orientation': 'landscape',
        'label': 'Pilot boat and cargo ship',
    },
}

FPS = 30
W, H = 960, 540
N_FRAMES = 150


def injected_motion(n: int = N_FRAMES, fps: int = FPS) -> tuple[np.ndarray, np.ndarray]:
    """Known global X/Y camera shake, intentionally added to source imagery."""
    t = np.arange(n, dtype=float) / float(fps)
    x = 3.0*np.sin(2*math.pi*.24*t) + 8.0*np.sin(2*math.pi*5.0*t) + 2.0*np.sin(2*math.pi*7.0*t)
    y = 2.0*np.sin(2*math.pi*.30*t) + 6.0*np.sin(2*math.pi*4.2*t) + 2.0*np.sin(2*math.pi*7.2*t)
    return x,y


def fit_letterbox(frame: np.ndarray, width: int=W, height: int=H) -> np.ndarray:
    """Retain the original aspect ratio, including portrait sources."""
    h,w=frame.shape[:2]
    if w<1 or h<1:raise ValueError('Invalid video frame dimensions')
    scale=min(width/w,height/h)
    nw,nh=max(1,int(round(w*scale))),max(1,int(round(h*scale)))
    im=cv2.resize(frame,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
    out=np.full((height,width,3), (24,32,40),dtype=np.uint8)
    x0,y0=(width-nw)//2,(height-nh)//2
    out[y0:y0+nh,x0:x0+nw]=im
    return out


def make_writer(path: Path, fps: int=FPS, width: int=W, height: int=H) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True,exist_ok=True)
    wr=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
    if not wr.isOpened():raise RuntimeError(f'Cannot open MP4 encoder for {path}')
    return wr


def prepare(source: Path, key: str, output_dir: Path, frames: int=N_FRAMES, fps: int=FPS) -> dict:
    if key not in SOURCES:raise ValueError(f'Unknown footage key: {key}')
    source=Path(source).expanduser().resolve()
    if not source.is_file():raise FileNotFoundError(f'Original source video missing: {source}')
    if source.suffix.lower() not in {'.mp4','.mov','.avi','.m4v'}:
        raise ValueError('Source must be a locally downloaded MP4/MOV/AVI/M4V video')
    if not (18 <= frames <= 496):raise ValueError('Choose 18–496 frames for the current FPGA protocol')
    info=SOURCES[key]
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened():raise RuntimeError(f'Cannot decode video: {source}')
    input_fps=float(cap.get(cv2.CAP_PROP_FPS))
    if not 1 <= input_fps <= 240:
        cap.release();raise ValueError(f'Invalid input video FPS: {input_fps}')
    frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count<=0:
        cap.release();raise ValueError('Source video has no decodable frames')
    source_duration=frame_count/input_fps
    duration=frames/fps
    if source_duration+0.05 < duration:
        cap.release();raise ValueError(f'Source video is only {source_duration:.2f}s, need {duration:.2f}s')
    # Use first five seconds for reproducibility rather than choosing a visually
    # favourable segment without reporting the selection.
    dest=Path(output_dir)/key
    dest.mkdir(parents=True,exist_ok=True)
    clean=dest/f'{key}_real_30fps.mp4'
    shaky=dest/f'{key}_real_with_injected_shake_30fps.mp4'
    traj=dest/f'{key}_known_injected_motion.csv'
    wr0=make_writer(clean,fps);wr1=make_writer(shaky,fps)
    x,y=injected_motion(frames,fps)
    src_idx=-1
    frame=None
    try:
        for i in range(frames):
            target=int(round(i*input_fps/fps))
            while src_idx < target:
                ok,current=cap.read()
                src_idx+=1
                if not ok or current is None:raise RuntimeError(f'Source ended while sampling output frame {i}')
                frame=current
            assert frame is not None
            corrected=fit_letterbox(frame)
            wr0.write(corrected)
            matrix=np.float32([[1,0,float(x[i])],[0,1,float(y[i])]])
            noisy=cv2.warpAffine(corrected,matrix,(W,H),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
            wr1.write(noisy)
    finally:
        wr0.release();wr1.release();cap.release()
    with traj.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['frame','x_pixels','y_pixels','x_q16_8','y_q16_8'])
        for i in range(frames):
            writer.writerow([i,f'{x[i]:.9f}',f'{y[i]:.9f}',int(round(x[i]*256)),int(round(y[i]*256))])
    record={
        **info,'original_video':str(source),'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'prepared_clean_video':str(clean),'prepared_test_video':str(shaky),'trajectory_csv':str(traj),
        'output_dimensions':[W,H],'output_fps':fps,'output_frames':frames,
        'method':'USER-SUPPLIED SOURCE FOOTAGE plus KNOWN INJECTED synthetic X/Y camera shake; no genuine vessel-measured motion is claimed',
        'license_reference':'https://www.pexels.com/license/',
        'notes':'Input is user-provided and declared to match the linked Pexels source; authenticity is not independently checked. Injected motion is synthetic; FPGA smooths numerical motion coordinates, never video pixels.'
    }
    (dest/'PROVENANCE.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return record


def main():
    ap=argparse.ArgumentParser(description='Prepare actual downloaded Pexels maritime clips for FPGA GUI')
    ap.add_argument('--ferry',type=Path,help='Downloaded source MP4 for ferry cargo-ship view')
    ap.add_argument('--pilot',type=Path,help='Downloaded source MP4 for pilot-boat/cargo ship')
    ap.add_argument('--out',type=Path,default=Path('build/real_maritime_clips'))
    args=ap.parse_args()
    if not args.ferry and not args.pilot:
        ap.error('Supply --ferry and/or --pilot with locally downloaded original clips')
    for key,source in [('ferry',args.ferry),('pilot',args.pilot)]:
        if source:
            result=prepare(source,key,args.out)
            print(key.upper(),'READY:',result['prepared_test_video'],'\ntrajectory:',result['trajectory_csv'])
    print('Use the prepared test video and its trajectory CSV in the GUI, or import directly from the Real Footage menu.')

if __name__=='__main__':main()

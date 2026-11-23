"""Prepare ORIGINAL naturally shaky footage without inserting or synthesising motion.

Only selects a time range, changes frame rate, scales/letterboxes to the GUI's
existing limits, and documents modifications. No artificial shake/CSV is made.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import cv2
import numpy as np
from audio_preservation import mux_original_audio

RAW_EXTENSIONS={'.mp4','.mov','.m4v','.avi','.webm','.mkv'}

def file_sha256(path:Path)->str:
    hasher=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def probe_raw(path:Path)->dict:
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    if path.suffix.lower() not in RAW_EXTENSIONS:
        raise ValueError(f'Unsupported input extension: {path.suffix}; expected {sorted(RAW_EXTENSIONS)}')
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('OpenCV cannot decode video; convert to MP4 with H.264 using another application')
    try:
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if width<20 or height<20 or not (1<=fps<=240) or count<18:
            raise ValueError(f'Invalid video metadata: {width}x{height}, {fps:.2f}fps, {count} frames')
        return dict(width=width,height=height,fps=fps,frames=count,duration_s=count/fps)
    finally:cap.release()


def _letterbox(frame:np.ndarray,width:int,height:int)->np.ndarray:
    h,w=frame.shape[:2]
    factor=min(width/w,height/h)
    nw=max(1,round(w*factor));nh=max(1,round(h*factor))
    small=cv2.resize(frame,(nw,nh),interpolation=cv2.INTER_AREA if factor<1 else cv2.INTER_LINEAR)
    out=np.full((height,width,3), (17,25,34),dtype=np.uint8)
    x=(width-nw)//2;y=(height-nh)//2
    out[y:y+nh,x:x+nw]=small
    return out


def prepare_natural_footage(source:Path,destination:Path,start_s:float=0.0,duration_s:float=5.0,
                            output_size=(960,540))->tuple[Path,dict]:
    """Convert original recording into 30fps supported video, no new camera movement.

    Nearest-timestamp source frames are retained/duplicated to match 30 fps.
    The original soundtrack is retained without applying noise filtering.
    """
    source=Path(source);destination=Path(destination)
    meta=probe_raw(source)
    if not (0.0<=start_s<meta['duration_s']):raise ValueError('Start is outside input video')
    duration=min(float(duration_s),meta['duration_s']-start_s,1500/30)
    n=int(math.floor(duration*30))
    if n<18:raise ValueError('Clip must have at least 18 output frames at 30fps')
    width,height=output_size
    if width>1280 or height>720 or width%2 or height%2:raise ValueError('Output resolution unsupported')
    destination.parent.mkdir(parents=True,exist_ok=True)
    cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_FRAMES,max(0,int(round(start_s*meta['fps']))-1))
    writer=cv2.VideoWriter(str(destination),cv2.VideoWriter_fourcc(*'mp4v'),30,(width,height))
    if not writer.isOpened():cap.release();raise RuntimeError('Cannot write MP4; verify OpenCV codec support')
    # Monotonic sequential reading is robust to codecs with inaccurate seeking.
    src_index=int(cap.get(cv2.CAP_PROP_POS_FRAMES))
    current=None;read_count=0
    try:
        for i in range(n):
            target=min(meta['frames']-1,int(round((start_s+i/30)*meta['fps'])))
            if target<src_index and current is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES,target);src_index=target
            while src_index<=target or current is None:
                ok,frame=cap.read()
                if not ok:break
                current=frame;src_index+=1;read_count+=1
            if current is None:raise ValueError('Input became unreadable during conversion')
            writer.write(_letterbox(current,width,height))
    finally:
        writer.release();cap.release()
    audio_info=mux_original_audio(destination,source,start_s=start_s)
    details={'source_kind':'REAL_VIDEO_USER_SUPPLIED_UNVERIFIED',
             'natural_motion':True,'injected_motion':False,
             'source_path':str(source),'source_sha256':file_sha256(source),
             'source_metadata':meta,'audio':audio_info,'clip_start_s':float(start_s),
             'clip_duration_s':n/30,'output_path':str(destination),
             'output_metadata':{'width':width,'height':height,'fps':30,'frames':n},
             'operations':['temporal_selection','nearest_timestamp_fps_normalisation','scale_preserve_aspect_letterbox'],
             'notes':'No camera shake has been added. No trajectory CSV supplied; motion estimated from decoded footage. Audio preserved when present, not filtered.',
             'licence':'User must hold source recording rights or verify the source licence; this tool does not grant redistribution rights.'}
    (destination.parent/(destination.stem+'_source_provenance.json')).write_text(json.dumps(details,indent=2)+'\n',encoding='utf8')
    return destination,details


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('source',type=Path);a.add_argument('--output',type=Path,default=Path('build/real_clip/natural_maritime.mp4'))
    a.add_argument('--start',type=float,default=0.);a.add_argument('--seconds',type=float,default=5.)
    q=a.parse_args();dst,d=prepare_natural_footage(q.source,q.output,q.start,q.seconds)
    print('PREPARED_UNMODIFIED_NATURAL_MOTION_VIDEO:',dst)
    print(json.dumps(d,indent=2))

if __name__=='__main__':main()

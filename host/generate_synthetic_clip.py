"""Reproducible maritime observation clip with known synthetic camera shake.

No real footage is included. Output frames represent the same fixed reference
world shifted by the supplied *true* camera translation trajectory.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import cv2
import numpy as np


def trajectory(n: int, fps: int = 30) -> tuple[np.ndarray, np.ndarray]:
    t=np.arange(n)/fps
    x=1.0*t + 3.2*np.sin(2*np.pi*0.23*t) + 10.0*np.sin(2*np.pi*5.0*t) + 3.5*np.sin(2*np.pi*8*t)
    y=1.5*np.sin(2*np.pi*0.3*t) + 7.0*np.sin(2*np.pi*4.2*t) + 2.7*np.sin(2*np.pi*7.2*t)
    return x,y


def make_scene(width:int=640,height:int=360)->np.ndarray:
    # Extra wide canvas for shift/crop safety. Ground-truth background landmarks.
    w=width+110;h=height+110;scene=np.empty((h,w,3),np.uint8)
    scene[:,:,:]=[200,175,132]  # BGR cloudy sky
    cv2.rectangle(scene,(0,220),(w,h),(132,87,47),-1)
    for i in range(19):
        x=i*49+10; cv2.line(scene,(x,227+(i%3)*2),(x+42,229-(i%2)*2),(210,178,120),2)
    # Distant working boat & navigation marker, always stationary in world.
    cv2.fillPoly(scene,[np.array([[295,215],[482,215],[460,241],[320,241]],dtype=np.int32)],(55,55,50))
    cv2.rectangle(scene,(422,190),(459,215),(220,220,218),-1)
    cv2.rectangle(scene,(435,180),(447,190),(205,205,200),-1)
    cv2.line(scene,(350,214),(350,157),(65,62,60),2)
    cv2.line(scene,(350,157),(387,184),(65,62,60),2)
    cv2.line(scene,(385,213),(385,151),(65,62,60),2)
    cv2.line(scene,(385,151),(420,180),(65,62,60),2)
    for x,y in [(115,150),(187,265),(535,167),(600,285),(675,165)]:
        cv2.drawMarker(scene,(x,y),(45,55,70),cv2.MARKER_CROSS,13,1)
    return scene


def generate(directory:Path,duration:float=5.0,fps:int=30)->tuple[Path,Path]:
    directory.mkdir(parents=True,exist_ok=True)
    width,height=640,360
    n=int(round(duration*fps))
    x,y=trajectory(n,fps)
    scene=make_scene(width,height)
    video=directory/'maritime_shaky_synthetic.mp4'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
    if not writer.isOpened():
        raise RuntimeError('OpenCV MP4 VideoWriter not available')
    for dx,dy in zip(x,y):
        matrix=np.float32([[1,0,float(dx)-55],[0,1,float(dy)-55]])
        frame=cv2.warpAffine(scene,matrix,(width,height),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        writer.write(frame)
    writer.release()
    path=directory/'ground_truth_trajectory.csv'
    with path.open('w',newline='',encoding='utf8') as f:
        out=csv.writer(f);out.writerow(['frame','x_pixels','y_pixels','x_q16_8','y_q16_8'])
        for i,(dx,dy) in enumerate(zip(x,y)):
            out.writerow([i,f'{dx:.9f}',f'{dy:.9f}',int(round(dx*256)),int(round(dy*256))])
    return video,path


def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,default=Path('build/maritime_demo'))
    a.add_argument('--seconds',type=float,default=5.0);p=a.parse_args()
    v,c=generate(p.out,p.seconds)
    print('Generated SOFTWARE-ONLY synthetic clip',v,'and ground-truth motion',c)
if __name__=='__main__':main()

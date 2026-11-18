"""v0.7: camera-centred SE(2) path estimation for short maritime footage.

The host estimates image-to-image rigid transforms from sparse optical flow.
Only X, Y and roll Q16.8 trajectories are sent to the existing FPGA FIR.
No video pixels enter the FPGA. Real scene motion can never be treated as
known ground-truth camera pose.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import cv2
import numpy as np
from motion_estimation import inspect_video


def _points(gray: np.ndarray, wide: bool = False):
    h,w=gray.shape
    mask=np.full((h,w),255,np.uint8)
    if not wide:
        # Moving vessel typically occupies central part; wake and waves the bottom.
        mask[int(h*.38):int(h*.91),int(w*.30):int(w*.71)]=0
    mask[:int(h*.035),:]=0
    return cv2.goodFeaturesToTrack(gray, maxCorners=650, qualityLevel=0.007,
                                    minDistance=7, blockSize=5, mask=mask)


def _rigid_from_affine(affine):
    """Remove estimated similarity scale: roll+translation only."""
    theta=float(np.arctan2(affine[1,0],affine[0,0]))
    c,s=np.cos(theta),np.sin(theta)
    step=np.eye(3,dtype=np.float64)
    step[:2,:2]=[[c,-s],[s,c]]
    step[:2,2]=affine[:2,2]
    return step, np.degrees(theta)


def estimate_three_axis(video: Path, trajectory: Path, diagnostics: Path | None = None) -> dict:
    """Output frame-centred absolute X/Y/roll trajectories as Q16.8 samples.

    The cumulative image-to-image transform maps coordinates from frame zero
    into the current frame. X/Y denote motion of the IMAGE CENTRE, not the
    translation column of a rotating affine matrix.
    """
    info=inspect_video(video)
    cap=cv2.VideoCapture(str(video));ok,first=cap.read()
    if not ok: raise ValueError('Video decode failed at first frame')
    prev=cv2.cvtColor(first,cv2.COLOR_BGR2GRAY)
    w,h=info.width,info.height
    center=np.array([w/2.,h/2.,1.],dtype=np.float64)
    total=np.eye(3,dtype=np.float64)
    trajectory_float=[(0.,0.,0.)]
    logs=[{'frame':0,'confidence':'REFERENCE','inlier_ratio':1.,'tracked':0,'accepted':True}]
    accepted=0;fallback=0;held=0
    try:
        for frame_n in range(1,info.frames):
            ok,frame=cap.read()
            if not ok:raise ValueError(f'Decode stopped at frame {frame_n}')
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            features=_points(prev)
            if features is None or len(features)<14:features=_points(prev,wide=True)
            step=np.eye(3,dtype=np.float64)
            rec={'frame':frame_n,'confidence':'LOW','inlier_ratio':0.,'tracked':0,'accepted':False,
                 'step_rotation_deg':0.,'fallback':''}
            if features is not None and len(features)>=9:
                kwargs=dict(winSize=(21,21),maxLevel=3,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,28,.01))
                nxt,valid,_=cv2.calcOpticalFlowPyrLK(prev,gray,features,None,**kwargs)
                if nxt is not None and valid is not None:
                    back,back_ok,_=cv2.calcOpticalFlowPyrLK(gray,prev,nxt,None,**kwargs)
                    if back is not None and back_ok is not None:
                        fb=np.linalg.norm(back.reshape(-1,2)-features.reshape(-1,2),axis=1)
                        keep=(valid.reshape(-1)>0)&(back_ok.reshape(-1)>0)&(fb<1.6)
                        pp=features.reshape(-1,2)[keep]
                        qq=nxt.reshape(-1,2)[keep]
                        rec['tracked']=len(pp)
                        if len(pp)>=8:
                            matrix,inliers=cv2.estimateAffinePartial2D(pp,qq,method=cv2.RANSAC,
                                ransacReprojThreshold=2.2,maxIters=1800,confidence=.995,refineIters=10)
                            if matrix is not None and inliers is not None:
                                ratio=float(np.mean(inliers))
                                rec['inlier_ratio']=round(ratio,4)
                                trial,rot=_rigid_from_affine(matrix)
                                if ratio>=.42 and abs(rot)<12 and np.linalg.norm(trial[:2,2])<125:
                                    step=trial;rec.update(confidence='HIGH' if ratio>=.65 else 'MEDIUM',
                                      accepted=True,step_rotation_deg=round(rot,5));accepted+=1
                            if not rec['accepted']:
                                displacement=np.median(qq-pp,axis=0)
                                if np.linalg.norm(displacement)<60:
                                    step[:2,2]=displacement
                                    rec['fallback']='median translation only (roll not trusted)'
                                    fallback+=1
            if not rec['accepted'] and not rec['fallback']:
                rec['fallback']='hold last camera pose (insufficient reliable features)';held+=1
            # Preserve geometric composition; do NOT sum the affine translation columns.
            total=step@total
            p=total@center
            theta=np.degrees(np.arctan2(total[1,0],total[0,0]))
            trajectory_float.append((float(p[0]-center[0]),float(p[1]-center[1]),float(theta)))
            logs.append(rec)
            prev=gray
    finally:cap.release()
    if len(trajectory_float)!=info.frames:raise AssertionError('Missing frames')
    trajectory=Path(trajectory);trajectory.parent.mkdir(parents=True,exist_ok=True)
    with trajectory.open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f)
        wr.writerow(['frame','x_pixels','y_pixels','theta_deg','x_q16_8','y_q16_8','theta_q16_8'])
        for idx,(x,y,theta) in enumerate(trajectory_float):
            q=[int(round(v*256)) for v in (x,y,theta)]
            if any(not -(1<<23)<=v<(1<<23) for v in q):
                raise ValueError('Camera trajectory exceeds signed 24-bit Q16.8 range')
            wr.writerow([idx,f'{x:.6f}',f'{y:.6f}',f'{theta:.6f}',*q])
    nsteps=max(1,info.frames-1)
    diag={'method':'host_opencv_bidirectional_flow_se2_three_axis',
      'frames':info.frames,'fps':info.fps,'ransac_steps':accepted,
      'fallback_steps':fallback,'held_steps':held,
      'high_confidence_fraction':round(accepted/nsteps,4),
      'low_confidence_fraction':round((fallback+held)/nsteps,4),
      'median_abs_roll_deg':float(np.median(np.abs(np.array(trajectory_float)[:,2]))),
      'warnings':[],
      'limitation':'Motion inferred from image content. Waves, cuts, blur and moving ships may corrupt estimates.'}
    if (fallback+held)/nsteps>.18:diag['warnings'].append('LOW MOTION-CONFIDENCE: >18% frame steps use fallback/hold')
    if held/nsteps>.05:diag['warnings'].append('FEATURE LOSS: >5% of steps had no usable pose update')
    if diagnostics:
        Path(diagnostics).write_text(json.dumps({'summary':diag,'frames':logs},indent=2)+'\n',encoding='utf-8')
    return diag

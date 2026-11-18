"""Independent *image-content* check of stabilisation after actual frame warping.

Not a ground-truth camera pose measurement. Uses Fourier phase correlation on
background image regions instead of the optical-flow/RANSAC estimation path.
If unsuitable footage yields unreliable matches, report INCONCLUSIVE.
"""
from __future__ import annotations
import json
from pathlib import Path
import cv2
import numpy as np


def _roi(gray:np.ndarray)->np.ndarray:
    h,w=gray.shape[:2]
    # Focus on background near the skyline and non-central edges. Avoid lower
    # moving water and (most) independently moving central ship pixels.
    # Upper-left + upper-right backgrounds included by a spatial mask.
    mask=np.zeros((h,w),dtype=np.float32)
    y0,y1=int(h*.08),int(h*.57)
    mask[y0:y1,int(w*.05):int(w*.94)]=1
    mask[y0:y1,int(w*.34):int(w*.66)]=0
    gray=cv2.resize(gray.astype(np.float32)*mask,(320,180),interpolation=cv2.INTER_AREA)
    return gray


def _trace(frames:list[np.ndarray])->dict:
    if len(frames)<18:return {'ok':False,'reason':'too few frames'}
    gray0=cv2.cvtColor(frames[0],cv2.COLOR_BGR2GRAY)
    h0,w0=gray0.shape
    patch=gray0[int(h0*.08):int(h0*.57),int(w0*.05):int(w0*.34)]
    if patch.size==0 or float(np.std(patch))<6.:
        return {'ok':False,'reason':'insufficient natural background texture for independent image-based measurement'}
    prev=_roi(gray0)
    hann=cv2.createHanningWindow((prev.shape[1],prev.shape[0]),cv2.CV_32F)
    increments=[];scores=[]
    for frame in frames[1:]:
        cur=_roi(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY))
        (dx,dy),response=cv2.phaseCorrelate(prev,cur,hann)
        increments.append((float(dx),float(dy)))
        scores.append(float(response));prev=cur
    increments=np.asarray(increments)
    scores=np.asarray(scores)
    valid=(scores>=.08) & (np.abs(increments).max(axis=1)<65)
    if valid.mean()<.80:
        return {'ok':False,'reason':'low independent image-registration confidence',
                'valid_pairs':int(valid.sum()),'pairs':len(valid),
                'median_response':float(np.median(scores))}
    # isolate fast frame-to-frame motion, suppressing gradual camera pan
    # through a 9-frame running baseline of step displacement.
    track=np.stack([increments[:,0],increments[:,1]],axis=1)
    def detrend(v):
        k=9;p=np.pad(v,(k//2,k//2),mode='edge')
        return v-np.convolve(p,np.ones(k)/k,mode='valid')
    hf=np.vstack([detrend(track[:,0]),detrend(track[:,1])]).T
    rms=float(np.sqrt(np.mean(np.square(hf[valid]))))
    return {'ok':True,'rms_high_frequency_registration_px':rms,
            'valid_pairs':int(valid.sum()),'pairs':len(valid),
            'median_response':float(np.median(scores))}


def compare_image_stability(side_by_side:Path, max_frames:int=496)->dict:
    """Measure residual image motion in original and corrected half-frames.

    The metric is independent of the FIR's numeric output but is still a
    proxy; for rotations or scenes with too little static texture it can fail.
    """
    cap=cv2.VideoCapture(str(side_by_side))
    if not cap.isOpened():return {'status':'INCONCLUSIVE','reason':'video decode failed'}
    before=[];after=[]
    try:
        for _ in range(max_frames):
            ok,frame=cap.read()
            if not ok:break
            w=frame.shape[1]//2
            if w<=0:break
            # top 28px contains synthetic caption bar. Crop it out in both.
            before.append(frame[30:, :w]);after.append(frame[30:,w:])
    finally:cap.release()
    a=_trace(before);b=_trace(after)
    if not (a['ok'] and b['ok']):return {'status':'INCONCLUSIVE','before':a,'after':b,
        'reason':'Insufficient reliable independent image registration; no image-based improvement claim.'}
    raw=a['rms_high_frequency_registration_px']
    stable=b['rms_high_frequency_registration_px']
    return {'status':'MEASURED','method':'background_masked_Fourier_phase_correlation',
            'before':a,'after':b,'reduction_pct':100*(1-stable/max(1e-9,raw)),
            'caveat':'Independent image-motion proxy, not absolute camera-pose truth; only translation is compensated.'}

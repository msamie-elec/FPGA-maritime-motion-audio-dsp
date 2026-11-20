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


def compare_image_stability(side_by_side: Path, max_frames: int = 1500) -> dict:
    """Stream only masked image ROIs to bound memory for long clips."""
    cap=cv2.VideoCapture(str(side_by_side))
    if not cap.isOpened():
        return {'status':'INCONCLUSIVE','reason':'video decode failed'}
    prev=None; steps=[[],[]]; scores=[[],[]]; frames=0; low_texture=False
    try:
        while frames<max_frames:
            ok,frame=cap.read()
            if not ok: break
            w=frame.shape[1]//2
            if w<20 or frame.shape[0]<55:
                return {'status':'INCONCLUSIVE','reason':'frame too small'}
            curr=[]
            for half in (frame[30:,:w],frame[30:,w:]):
                gray=cv2.cvtColor(half,cv2.COLOR_BGR2GRAY)
                h,ww=gray.shape
                patch=gray[int(h*.08):int(h*.57),int(ww*.05):int(ww*.34)]
                if frames==0 and (patch.size==0 or float(np.std(patch))<6):
                    low_texture=True
                curr.append(_roi(gray))
            if prev is not None:
                for i in (0,1):
                    hann=cv2.createHanningWindow((curr[i].shape[1],curr[i].shape[0]),cv2.CV_32F)
                    (dx,dy),quality=cv2.phaseCorrelate(prev[i],curr[i],hann)
                    steps[i].append((float(dx),float(dy)))
                    scores[i].append(float(quality))
            prev=curr
            frames+=1
    finally:
        cap.release()
    if low_texture:
        return {'status':'INCONCLUSIVE','reason':'insufficient background texture'}
    def summarise(i):
        if frames<18:return {'ok':False,'reason':'too few frames'}
        points=np.asarray(steps[i],dtype=float)
        conf=np.asarray(scores[i],dtype=float)
        valid=(conf>=.08)&(np.abs(points).max(axis=1)<65)
        if valid.mean()<.80:
            return {'ok':False,'reason':'low independent image registration confidence',
                    'valid_pairs':int(valid.sum()),'pairs':len(valid),
                    'median_response':float(np.median(conf))}
        def detrend(v):
            k=9
            return v-np.convolve(np.pad(v,(k//2,k//2),mode='edge'),np.ones(k)/k,mode='valid')
        jitter=np.column_stack([detrend(points[:,0]),detrend(points[:,1])])
        return {'ok':True,'rms_high_frequency_registration_px':float(np.sqrt(np.mean(np.square(jitter[valid])))),
                'valid_pairs':int(valid.sum()),'pairs':len(valid),
                'median_response':float(np.median(conf))}
    before,after=summarise(0),summarise(1)
    if not (before['ok'] and after['ok']):
        return {'status':'INCONCLUSIVE','before':before,'after':after,
                'reason':'Insufficient independent registration; no image-improvement claim.'}
    raw=before['rms_high_frequency_registration_px']
    stable=after['rms_high_frequency_registration_px']
    return {'status':'MEASURED','method':'streamed_masked_Fourier_phase_correlation',
            'before':before,'after':after,
            'reduction_pct':100*(1-stable/max(1e-9,raw)),
            'caveat':'Proxy for residual image motion, not camera-pose ground truth.'}

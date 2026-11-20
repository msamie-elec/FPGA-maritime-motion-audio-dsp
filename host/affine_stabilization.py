"""v0.7: three-axis camera correction using existing FIR numerical path.

This is buffered *host-side* geometry. All filtered X/Y/roll numbers are
produced by the actual FPGA in hardware mode (each job checked bit-exact),
while OpenCV performs frame resampling on the PC.
"""
from __future__ import annotations
import csv,json
from pathlib import Path
import numpy as np
import cv2
from stabilize_video import smooth_trajectory,evaluate
from audio_preservation import mux_original_audio

AXES=('x','y','theta')


def read_path(path:Path)->dict[str,list[int]]:
    with Path(path).open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    if not rows or not {'x_q16_8','y_q16_8','theta_q16_8'}<=set(rows[0]):
        raise ValueError('Three-axis CSV requires x_q16_8, y_q16_8, theta_q16_8')
    return {'x':[int(r['x_q16_8']) for r in rows],
            'y':[int(r['y_q16_8']) for r in rows],
            'theta':[int(r['theta_q16_8']) for r in rows]}


def smooth_axes(raw:dict,port:str|None,profile:str='Normal') -> dict:
    if profile not in ('Normal','Strong'):
        raise ValueError('Profile must be Normal or Strong')
    filtered={}
    for axis_id,axis in enumerate(AXES,1):
        signal=raw[axis]
        first=smooth_trajectory(signal,port,axis_id)
        filtered[axis]=(smooth_trajectory(first,port,axis_id+3)
                         if profile=='Strong' else first)
    return filtered


def pose_matrix(x:float,y:float,theta_deg:float,width:int,height:int)->np.ndarray:
    """Maps frame-zero coordinates to a camera path image (center-relative)."""
    center=(width*.5,height*.5)
    a=cv2.getRotationMatrix2D(center,-theta_deg,1.)
    # cv2 rotation matrix convention uses opposite sign to positive image-space roll.
    a[0,2]+=x;a[1,2]+=y
    return np.vstack([a,[0.,0.,1.]])


def correction_matrices(raw:dict, filt:dict,width:int,height:int)->list[np.ndarray]:
    """Correct current frame from raw C_i to desired smoothed S_i: W=S_i@inv(C_i)."""
    n=len(raw['x']);out=[]
    for i in range(n):
        p=[raw[k][i]/256.0 for k in AXES]
        q=[filt[k][i]/256.0 for k in AXES]
        original=pose_matrix(*p,width,height)
        smoothed=pose_matrix(*q,width,height)
        a=smoothed@np.linalg.inv(original)
        out.append(a[:2].astype(np.float32))
    return out


def required_crop(warps:list[np.ndarray],width:int,height:int,min_retained_fraction=.72)->dict:
    """Largest centred square-aspect crop whose corners remain inside all warped frames.

    Use a *fixed* crop for entire video so the zoom itself never vibrates.
    If excessive cropping would be required, report and use reflected borders
    rather than claiming every destination pixel was genuine observed content.
    """
    if not warps:raise ValueError('No transforms')
    raw=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    polygons=[cv2.transform(raw[None,:,:],m)[0].astype(np.float32) for m in warps]
    cx,cy=(width-1)/2.,(height-1)/2.
    def fits(frac):
        hx=(width-1)*frac/2;hy=(height-1)*frac/2
        pts=((cx-hx,cy-hy),(cx+hx,cy-hy),(cx+hx,cy+hy),(cx-hx,cy+hy))
        for polygon in polygons:
            if any(cv2.pointPolygonTest(polygon,p,False)<-1e-5 for p in pts):return False
        return True
    if not fits(min_retained_fraction):
        return {'fraction':1.,'area_retained_pct':100.,'valid_fov':False,
                'warning':f'Would require >{(1-min_retained_fraction)*100:.0f}% linear crop; reflected borders used instead'}
    lo=min_retained_fraction;hi=1.
    for _ in range(15):
        mid=(hi+lo)/2
        if fits(mid):lo=mid
        else:hi=mid
    return {'fraction':round(lo,5),'area_retained_pct':round(100*lo*lo,2),'valid_fov':True,
            'warning':None}


def stabilise_affine(video_path:Path,trajectory_path:Path,output_dir:Path,
                      port:str|None,profile='Normal'):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    raw=read_path(trajectory_path)
    filtered=smooth_axes(raw,port,profile)
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise RuntimeError('Unable to decode video')
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 30.)
    if any(len(v)!=len(raw['x']) for v in raw.values()):raise ValueError('Mismatched input axis lengths')
    warps=correction_matrices(raw,filtered,width,height)
    crop=required_crop(warps,width,height)
    outpath=output_dir/('fpga_before_after.mp4' if port else 'software_preview_before_after.mp4')
    writer=cv2.VideoWriter(str(outpath),cv2.VideoWriter_fourcc(*'mp4v'),fps,(2*width,height))
    if not writer.isOpened():cap.release();raise RuntimeError('Cannot create output MP4')
    n=0;shift=[]
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            if n>=len(warps):raise RuntimeError('Video contains more frames than trajectory')
            # transform maps input pixels into desired output pixels.
            out=cv2.warpAffine(frame,warps[n],(width,height),flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT_101)
            frac=crop['fraction'];cw=int(width*frac);ch=int(height*frac)
            if cw<width or ch<height:
                x0=(width-cw)//2;y0=(height-ch)//2
                # Apply *same* fixed crop to both source and corrected comparisons.
                frame=cv2.resize(frame[y0:y0+ch,x0:x0+cw],(width,height))
                out=cv2.resize(out[y0:y0+ch,x0:x0+cw],(width,height))
            pair=np.hstack((frame,out))
            label='FPGA FILTERED' if port else 'SOFTWARE REFERENCE'
            for offset,title in ((0,'ORIGINAL - CAMERA'),(width,'STABILISED - '+label)):
                cv2.rectangle(pair,(offset,0),(offset+width,28),(18,36,53),-1)
                cv2.putText(pair,title,(offset+12,20),cv2.FONT_HERSHEY_SIMPLEX,.50,(245,245,245),1,cv2.LINE_AA)
            writer.write(pair)
            shift.append(float(np.linalg.norm(warps[n][:,2])))
            n+=1
    finally:
        cap.release();writer.release()
    if n!=len(warps):raise RuntimeError(f'Wrong decoded-frame count {n} vs {len(warps)}')
    audio_info=mux_original_audio(outpath,video_path)
    mode='PHYSICAL FPGA - BIT-EXACT VERIFIED' if port else 'SOFTWARE REFERENCE ONLY'
    measures={a:evaluate(raw[a],filtered[a]) for a in AXES}
    m={'mode':mode,'frames':n,'source_video':Path(video_path).name,'physical_port':port,
       **measures,'pass_target_30pct':all(measures[a]['reduction_pct']>=30 for a in AXES),
       'stabilisation_version':'v0.7_se2_affine','profile':profile,
       'crop':crop,'audio':audio_info,'correction_magnitude':{'mean_translation_column_px':float(np.mean(shift)),
                                            'max_translation_column_px':float(np.max(shift))},
       'filtered_axes':list(AXES),
       'geometry':'S_i @ inverse(C_i), with centre-relative X/Y and image-plane roll',
       'caveat':'Crop and image stability are separate metrics; smoothing trajectories is not proof of visual success.'}
    (output_dir/'metrics.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    (output_dir/'filtered_trajectory.json').write_text(json.dumps({'mode':mode,**filtered},indent=2)+'\n',encoding='utf-8')
    return outpath,m

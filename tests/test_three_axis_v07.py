"""Three-axis geometry and FIR integration tests; do not claim physical hardware."""
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from affine_stabilization import (pose_matrix, correction_matrices, read_path,
                                  required_crop, smooth_axes)
from motion_estimation_v07 import estimate_three_axis
from gui_pipeline import run_pipeline


def _jitter_clip(path,frames=75,w=400,h=260):
    rng=np.random.default_rng(18)
    background=rng.integers(70,220,(h,w,3),dtype=np.uint8)
    # stationary background with stable corner texture and a horizon-like edge
    cv2.line(background,(0,105),(w,105),(25,40,60),3)
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),30,(w,h))
    assert writer.isOpened()
    positions=[]
    for i in range(frames):
        x=5*np.sin(i*.56);y=3*np.cos(i*.67)-3
        roll=2.5*np.sin(i*.55)
        transform=pose_matrix(x,y,roll,w,h)
        frame=cv2.warpAffine(background,transform[:2],(w,h),borderMode=cv2.BORDER_REFLECT_101)
        writer.write(frame);positions.append((x,y,roll))
    writer.release()
    return np.asarray(positions)


def test_rigid_geometry_correction_exact():
    w,h=480,270
    raw={"x":[0,256*11],"y":[0,-6*256],"theta":[0,round(4.5*256)]}
    target={k:[0,0] for k in raw}
    transforms=correction_matrices(raw,target,w,h)
    measured=pose_matrix(11,-6,4.5,w,h)
    assert np.allclose(np.vstack((transforms[1],[0,0,1]))@measured,np.eye(3),atol=.025)


def test_crop_contract():
    w,h=460,270
    shift=np.float32([[1,0,12],[0,1,-8]])
    crop=required_crop([np.float32([[1,0,0],[0,1,0]]),shift],w,h)
    assert crop['valid_fov'] is True
    assert .75<crop['fraction']<1
    impossible=required_crop([np.float32([[1,0,250],[0,1,0]])],w,h)
    assert impossible['valid_fov'] is False and impossible['warning']


def test_roll_and_translations_are_estimated(tmp_path):
    video=tmp_path/'rotated.mp4';truth=_jitter_clip(video,frames=75)
    path=tmp_path/'path.csv';diag=estimate_three_axis(video,path,tmp_path/'quality.json')
    values=read_path(path)
    assert len(values['theta'])==75 and diag['ransac_steps']>=65
    for axis,idx,tolerance in [('x',0,2.6),('y',1,2.6),('theta',2,.75)]:
        observed=np.asarray(values[axis])/256.
        error=observed-truth[:,idx]
        assert np.sqrt(np.mean(error**2))<tolerance,(axis,np.sqrt(np.mean(error**2)))


def test_two_pass_fir_jobs_are_distinct(monkeypatch):
    calls=[]
    def substitute(samples,port,axis_id):
        calls.append((axis_id,port))
        return list(samples)
    monkeypatch.setattr('affine_stabilization.smooth_trajectory',substitute)
    raw={k:[0,100,-200,0] for k in ('x','y','theta')}
    got=smooth_axes(raw,'COM4','Strong')
    assert got==raw
    assert [v[0] for v in calls]==[1,4,2,5,3,6]


def test_end_to_end_three_axis_software_ref(tmp_path):
    video=tmp_path/'rotated.mp4';_jitter_clip(video,frames=75)
    out=run_pipeline(video,None,tmp_path/'out',None,profile='Strong')
    assert out.metrics['stabilisation_version']=='v0.7_se2_affine'
    assert out.metrics['profile']=='Strong' and out.metrics['hardware_verified'] is False
    assert len(out.filtered_trajectory['theta'])==75
    assert (out.output_dir/'roll_comparison.png').exists()
    assert (out.output_dir/'motion_estimation_diagnostics.json').exists()
    assert out.metrics['theta']['reduction_pct']>0
    assert out.side_by_side.exists()
    assert out.metrics['crop']['area_retained_pct']>0

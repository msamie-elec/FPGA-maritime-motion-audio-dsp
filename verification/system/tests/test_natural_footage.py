from __future__ import annotations
import sys,json
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from prepare_natural_footage import prepare_natural_footage,probe_raw,file_sha256
from gui_pipeline import prepare_video,run_pipeline
from image_stability import compare_image_stability


def make_camera_file(path:Path,fps=24,frames=108):
    w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(200,140))
    assert w.isOpened()
    rng=np.random.default_rng(42)
    background=rng.integers(60,220,(140,200,3),dtype=np.uint8)
    for i in range(frames):
        dx=int(4*np.sin(i*.8));dy=int(3*np.cos(i*.9))
        moved=cv2.warpAffine(background,np.float32([[1,0,dx],[0,1,dy]]),(200,140),borderMode=cv2.BORDER_REFLECT_101)
        w.write(moved)
    w.release()


def test_real_import_does_not_add_shake_or_csv(tmp_path):
    raw=tmp_path/'source.mp4';make_camera_file(raw)
    dest=tmp_path/'normalised.mp4'
    dst,meta=prepare_natural_footage(raw,dest,start_s=.5,duration_s=2)
    assert dst.is_file() and meta['injected_motion'] is False
    assert meta['source_sha256']==file_sha256(raw)
    assert meta['source_kind']=='REAL_VIDEO_USER_SUPPLIED_UNVERIFIED'
    assert meta['output_metadata']['fps']==30
    assert 'source_provenance' in str(next(tmp_path.glob('*provenance.json')))
    assert not (tmp_path/'normalised.csv').exists()
    _,traj,evidence=prepare_video(dest,None,tmp_path/'out')
    assert evidence['method']=='host_opencv_bidirectional_flow_se2_three_axis'
    assert traj.exists()


def test_photometric_stability_measure_fails_honestly_on_blank_clip(tmp_path):
    pair=tmp_path/'pair.mp4'
    w=cv2.VideoWriter(str(pair),cv2.VideoWriter_fourcc(*'mp4v'),30,(320,120))
    for i in range(30):
        w.write(np.full((120,320,3),155,dtype=np.uint8))
    w.release()
    report=compare_image_stability(pair)
    assert report['status']=='INCONCLUSIVE'


def test_real_import_pipeline_labeled_automated_no_csv(tmp_path):
    raw=tmp_path/'raw.mp4';make_camera_file(raw,fps=30,frames=90)
    dst,_=prepare_natural_footage(raw,tmp_path/'input.mp4',duration_s=3)
    result=run_pipeline(dst,None,tmp_path/'processed',None)
    assert result.metrics['input_type']=='AUTO_ESTIMATION_NO_INJECTED_MOTION'
    assert result.metrics['hardware_verified'] is False
    assert 'image_stability' in result.metrics
    assert result.side_by_side.exists()

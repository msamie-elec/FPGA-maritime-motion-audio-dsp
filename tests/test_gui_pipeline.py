"""Host-side GUI pipeline tests. None of these asserts physical FPGA success."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from gui_pipeline import prepare_video, run_pipeline
from motion_estimation import inspect_video, estimate_translation
from generate_synthetic_clip import generate
from stabilize_video import inputs_from_csv


def test_user_video_motion_estimation_and_software_pipeline(tmp_path):
    video,gt=generate(tmp_path/'source',duration=3.0)
    info=inspect_video(video)
    assert info.frames==90 and info.fps==30
    out_csv=tmp_path/'estimated.csv'
    diag=estimate_translation(video,out_csv)
    assert diag['ransac_steps']>=80
    expected_x,expected_y=inputs_from_csv(gt)
    actual_x,actual_y=inputs_from_csv(out_csv)
    # Estimated relative motion is noisy due to video compression; 2 px RMS is acceptable.
    for actual,expected in ((actual_x,expected_x),(actual_y,expected_y)):
        err=(np.array(actual)-np.array(expected))/256
        assert np.sqrt(np.mean(err**2))<2.0
    result=run_pipeline(video,None,tmp_path/'processed',port=None)
    assert result.metrics['mode']=='SOFTWARE REFERENCE ONLY'
    assert result.metrics['hardware_verified'] is False
    assert result.metrics['frames']==90
    assert result.metrics['x']['reduction_pct']>50
    assert result.metrics['y']['reduction_pct']>50
    assert result.side_by_side.is_file()
    cap=cv2.VideoCapture(str(result.side_by_side))
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==90
    assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))==1280
    cap.release()


def test_supplied_trajectory_skips_estimation(tmp_path):
    v,t=generate(tmp_path/'source',duration=2.0)
    vv,tt,diag=prepare_video(v,t,tmp_path/'out')
    assert vv==v and tt==t
    assert diag['method']=='user_supplied_trajectory_csv'


def test_reject_incorrect_fps(tmp_path):
    path=tmp_path/'wrong_fps.mp4'
    w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),25,(120,80))
    assert w.isOpened()
    for i in range(30):
        w.write(np.zeros((80,120,3),dtype=np.uint8))
    w.release()
    with pytest.raises(ValueError,match='fps'):
        inspect_video(path)


def test_cannot_mislabel_software_as_hardware(tmp_path):
    r=run_pipeline(None,None,tmp_path/'demo',port=None)
    assert r.metrics['mode']=='SOFTWARE REFERENCE ONLY'
    assert r.metrics['hardware_verified'] is False
    assert r.metrics['estimation']['method']=='known_synthetic_ground_truth'

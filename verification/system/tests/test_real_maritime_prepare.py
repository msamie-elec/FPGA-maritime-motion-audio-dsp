"""Video preparation tests use small generated video FIXTURES, never claim Pexels original footage."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from prepare_real_maritime_clips import prepare, fit_letterbox, SOURCES, injected_motion
from motion_estimation import inspect_video


def _fixture(path: Path, fps: int=60, count: int=85, portrait=False):
    w,h=(120,170) if portrait else (200,110)
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    assert writer.isOpened()
    for i in range(count):
        frame=np.full((h,w,3),(40,120,200),dtype=np.uint8)
        cv2.line(frame,(0,20+(i%5)),(w-1,20+(i%5)),(255,255,255),3)
        cv2.rectangle(frame,(int(w*.25),int(h*.4)),(int(w*.8),int(h*.6)),(35,45,60),-1)
        writer.write(frame)
    writer.release()


def test_aspect_ratio_and_motion():
    p=fit_letterbox(np.zeros((192,108,3),dtype=np.uint8))
    assert p.shape==(540,960,3)
    assert tuple(p[270,40])==(24,32,40) # letterboxed side bar
    x,y=injected_motion(30,30)
    assert len(x)==30 and len(y)==30 and x[0]==0 and y[0]==0


def test_prepare_both_sources_from_local_test_fixtures(tmp_path):
    for key, portrait in [('ferry',True),('pilot',False)]:
        src=tmp_path/f'{key}_fake_test_fixture.mp4'
        _fixture(src,fps=60,count=68,portrait=portrait)
        meta=prepare(src,key,tmp_path/'out',frames=30)
        assert meta['output_frames']==30 and meta['output_fps']==30
        for file_key in ['prepared_clean_video','prepared_test_video']:
            info=inspect_video(Path(meta[file_key]))
            assert info.frames==30 and info.fps==30 and (info.width,info.height)==(960,540)
        with Path(meta['trajectory_csv']).open(newline='') as file:
            rows=list(csv.DictReader(file))
        assert len(rows)==30 and int(rows[0]['x_q16_8'])==0
        info=json.loads((Path(meta['trajectory_csv']).parent/'PROVENANCE.json').read_text())
        assert info['source_id']==SOURCES[key]['source_id']
        assert 'INJECTED' in info['method']


def test_missing_original_error(tmp_path):
    try:
        prepare(tmp_path/'not_here.mp4','ferry',tmp_path/'out')
    except FileNotFoundError as exc:
        assert 'missing' in str(exc)
    else:
        assert False,'Expected missing source failure'


def test_prepared_trajectory_through_existing_software_video_pipeline(tmp_path):
    """Integration fixture only: generated pixels, not a genuine maritime source."""
    from gui_pipeline import run_pipeline
    source=tmp_path/'fixture_clip.mp4'
    _fixture(source,fps=60,count=68,portrait=False)
    prepared=prepare(source,'pilot',tmp_path/'out',frames=30)
    result=run_pipeline(Path(prepared['prepared_test_video']),Path(prepared['trajectory_csv']),tmp_path/'result',port=None)
    assert result.side_by_side.is_file()
    assert result.metrics['frames']==30
    assert result.metrics['hardware_verified'] is False
    assert result.metrics['mode']=='SOFTWARE REFERENCE ONLY'
    assert result.metrics['estimation']['method']=='user_supplied_trajectory_csv'

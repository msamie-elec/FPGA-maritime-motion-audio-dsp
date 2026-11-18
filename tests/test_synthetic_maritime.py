from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from generate_synthetic_clip import trajectory
from stabilize_video import evaluate,smooth_trajectory


def test_trajectory_fir_rejects_fast_motion():
    x,y=trajectory(150)
    for axis in (x,y):
        samples=[int(round(float(v)*256)) for v in axis]
        out=smooth_trajectory(samples)
        assert len(out)==len(samples)
        assert evaluate(samples,out)['reduction_pct']>=30


def test_video_filter_constant_input():
    raw=[1234]*150
    assert smooth_trajectory(raw)==raw

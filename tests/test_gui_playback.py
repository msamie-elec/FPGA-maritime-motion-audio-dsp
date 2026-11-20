"""GUI playback regression — run with a display (Xvfb on Linux).

This is video-player-only validation, not an FPGA or video-stabilisation test.
"""
from __future__ import annotations
import sys
from pathlib import Path
import tkinter as tk
from unittest.mock import patch

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from maritime_gui import MaritimeGUI


@pytest.fixture
def ui():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk requires a desktop display (or xvfb-run).')
    app = MaritimeGUI(root)
    root.update()
    try:
        yield app
    finally:
        app._release_video()
        try:
            root.destroy()
        except tk.TclError:
            pass


def make_clip(path: Path, *, pair: bool = False, frames: int = 30) -> Path:
    width, height = (320 if pair else 160), 90
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 30, (width, height))
    assert writer.isOpened()
    for i in range(frames):
        img = np.zeros((height, width, 3), np.uint8)
        img[:, :, 0] = (i * 7) % 256
        cv2.circle(img, (30 + i % 80, 40), 10, (0, 180, 240), -1)
        if pair:
            cv2.rectangle(img, (160, 0), (319, 89), (35, 100 + i * 3 % 155, 70), -1)
        writer.write(img)
    writer.release()
    return path


def player_tick(app: MaritimeGUI) -> None:
    """Simulate precisely one presentation frame, independently of CPU speed.

    The player intentionally follows elapsed *wall-clock* time so that video
    stays synchronised with the soundtrack: a slow Windows redraw may skip
    frames.  Freeze monotonic time for this one test callback instead of
    expecting an exact frame number after real-time decoding/resizing.
    """
    app._cancel_play_timer()
    elapsed = 1.01 / app.fps
    fake_time = app._play_start + elapsed
    with patch('maritime_gui.time.monotonic', return_value=fake_time):
        app._play_tick()


def test_open_video_can_play_before_filtering(ui, tmp_path, monkeypatch):
    path = make_clip(tmp_path / 'source.mp4')
    monkeypatch.setattr('maritime_gui.filedialog.askopenfilename', lambda **_: str(path))
    ui.choose_video()
    assert ui.result is None
    assert ui._playback_kind == 'source'
    assert ui.capture is not None and ui.frames == 30
    assert 'disabled' not in ui.play_btn.state()
    assert 'Process this video' in ui.right.cget('text')
    assert ui._img_left is not None
    ui.toggle_play()
    assert ui.playing
    player_tick(ui)
    assert ui.frame_idx == 1
    ui.toggle_play()
    assert not ui.playing and ui._play_after_id is None
    ui.seek_pos.set(16)
    ui._seek_release()
    assert ui.frame_idx == 16 and not ui.playing


def test_replay_after_end_and_seek_to_final_frame(ui, tmp_path):
    path = make_clip(tmp_path / 'comparison.mp4', pair=True)
    ui._open_pair_video(path)
    assert ui._playback_kind == 'pair'
    assert ui._img_left is not None and ui._img_right is not None
    ui._show_frame(ui.frames - 2)
    ui.toggle_play()
    player_tick(ui)
    assert ui.frame_idx == ui.frames - 1
    assert not ui.playing
    assert 'Replay' in ui.play_btn.cget('text')
    ui.toggle_play()
    assert ui.playing and ui.frame_idx == 0
    player_tick(ui)
    assert ui.frame_idx == 1
    ui._pause_playback()
    ui.seek_pos.set(ui.frames - 1)
    ui._seek_release()
    assert 'Replay' in ui.play_btn.cget('text')
    ui.toggle_play()
    assert ui.frame_idx == 0 and ui.playing
    ui._pause_playback()


def test_replace_and_reset_source_cancels_old_timer(ui, tmp_path):
    first = make_clip(tmp_path / 'a.mp4')
    second = make_clip(tmp_path / 'b.mp4', frames=42)
    ui.source = first
    ui._show_source_frame()
    ui.toggle_play()
    assert ui._play_after_id is not None
    ui.source = second
    ui._clear_result()
    ui._show_source_frame()
    assert ui.frames == 42 and ui.frame_idx == 0
    assert ui._play_after_id is None and not ui.playing
    assert 'disabled' not in ui.play_btn.state()
    ui.reset_view()
    assert ui.frames == 42 and ui._playback_kind == 'source'
    ui.toggle_play()
    player_tick(ui)
    assert ui.frame_idx == 1
    ui._pause_playback()

"""v0.8.2 long-video packet overlap and audio integrity (software tests)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "host"))
import numpy as np
import pytest
from fixed_point_golden import FirReference, centered_smooth
import stabilize_video


@pytest.mark.parametrize("n", [18, 149, 496, 497, 906, 1500])
def test_hardware_packet_overlap_matches_continuous_fir(monkeypatch, n):
    # Mock is a numeric FIR *test fixture*; not real FPGA evidence.
    seen = []
    def fake_batch(port, payload, job_id):
        assert port == "TEST-COM"
        assert len(payload) <= 512
        seen.append((job_id, len(payload)))
        return FirReference().process(payload)
    import fpga_serial_client
    monkeypatch.setattr(fpga_serial_client, "run_batch", fake_batch)
    values = [int(round(14000 * np.sin(i * .2) + 3000 * np.cos(i * .13))) for i in range(n)]
    assert stabilize_video.smooth_trajectory(values, "TEST-COM", axis_id=3) == centered_smooth(values)
    assert len(seen) == (n+495)//496
    assert all(j == 3 for j,_ in seen)


def test_long_input_video_is_accepted(tmp_path):
    import cv2
    from motion_estimation import inspect_video
    path=tmp_path/"long.mp4"
    writer=cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (96,72))
    assert writer.isOpened()
    for i in range(520):
        frame=np.zeros((72,96,3),dtype=np.uint8)
        frame[12:30, (i//3)%60:(i//3)%60+20] = 255
        writer.write(frame)
    writer.release()
    assert inspect_video(path).frames == 520


def test_audio_preserved_in_export(tmp_path):
    import cv2, subprocess
    from audio_preservation import _ffmpeg, source_has_audio, mux_original_audio
    ffmpeg=_ffmpeg()
    source=tmp_path/"audio_source.m4a"
    r=subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-y",
                     "-f","lavfi","-i","sine=frequency=440:duration=1",
                     "-c:a","aac",str(source)],capture_output=True,text=True)
    if r.returncode!=0:
        pytest.skip("FFmpeg binary has no lavfi sine source")
    silent=tmp_path/"output.mp4"
    writer=cv2.VideoWriter(str(silent),cv2.VideoWriter_fourcc(*"mp4v"),30,(96,72))
    assert writer.isOpened()
    for i in range(30):
        writer.write(np.zeros((72,96,3),dtype=np.uint8))
    writer.release()
    assert source_has_audio(source)
    result=mux_original_audio(silent,source)
    assert result["audio_preserved"] is True
    assert source_has_audio(silent)

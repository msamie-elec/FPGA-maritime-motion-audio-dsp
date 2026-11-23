"""Unified AV acceptance tests, using generated media and an explicitly MOCKED UART.

These tests do not prove FPGA hardware, speech intelligibility or real video quality.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import wave

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from generate_synthetic_clip import generate
from audio_dsp import FS
from audio_preservation import _ffmpeg, source_has_audio
from fixed_point_golden import FirReference
from design_audio_coefficients import design
from unified_pipeline import run_unified_pipeline


def make_video_with_audio(tmp_path:Path,seconds=1.0):
    video,trajectory=generate(tmp_path, duration=seconds)
    n=round(FS*seconds)
    t=np.arange(n)/FS
    samples=(7000*np.sin(2*np.pi*800*t)+1800*np.sin(2*np.pi*6000*t)).astype('<i2')
    import wave
    wav=tmp_path/'test_audio.wav'
    with wave.open(str(wav),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(FS);out.writeframes(samples.tobytes())
    media=tmp_path/'test_with_audio.mp4'
    r=subprocess.run([_ffmpeg(),'-loglevel','error','-y','-i',str(video),'-i',str(wav),
                      '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac',
                      '-shortest',str(media)],capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stderr
    return media,trajectory


def test_combined_rejects_silent_source(tmp_path):
    source,trajectory=generate(tmp_path,duration=1.)
    with pytest.raises(ValueError,match='no audio track'):
        run_unified_pipeline(source,trajectory,tmp_path/'rejected',port=None)


def test_combined_software_creates_single_av_output(tmp_path):
    source,trajectory=make_video_with_audio(tmp_path)
    out=tmp_path/'combined'
    result=run_unified_pipeline(source,trajectory,out,port=None)
    assert result.metrics['combined_processing']=='Video + Audio'
    assert result.metrics['audio_filtering']['status']=='SOFTWARE REFERENCE ONLY'
    assert result.metrics['combined_hardware_verified'] is False
    assert result.metrics['hardware_verified'] is False
    assert (out/'final_stabilised_filtered_audio.mp4').is_file()
    assert source_has_audio(out/'final_stabilised_filtered_audio.mp4')
    assert source_has_audio(result.side_by_side)
    assert (out/'audio_original.wav').is_file()
    assert (out/'audio_filtered.wav').is_file()
    assert (out/'audio_AB_compare.wav').is_file()
    assert (out/'audio_analysis.png').is_file()
    assert (out/'combined_metrics.json').is_file()
    assert result.metrics['audio_filtering']['samples']==FS
    assert result.metrics['audio_filtering']['decoded_audio_samples'] <= FS
    assert result.metrics['audio_filtering']['audio_end_silence_padding_samples'] == (
        FS-result.metrics['audio_filtering']['decoded_audio_samples'])
    original=cv2.VideoCapture(str(source))
    final=cv2.VideoCapture(str(out/'final_stabilised_filtered_audio.mp4'))
    assert abs(original.get(cv2.CAP_PROP_FRAME_COUNT)-final.get(cv2.CAP_PROP_FRAME_COUNT))<=1
    assert final.get(cv2.CAP_PROP_FRAME_WIDTH)==640
    assert final.get(cv2.CAP_PROP_FRAME_HEIGHT)==360
    original.release();final.release()


def test_video_only_preserves_original_audio(tmp_path):
    source,trajectory=make_video_with_audio(tmp_path)
    result=run_unified_pipeline(source,trajectory,tmp_path/'video_only',port=None,processing='Video only')
    assert source_has_audio(result.side_by_side)
    assert not (result.output_dir/'audio_filtered.wav').exists()
    assert result.metrics['audio_filtering']['status']=='NOT REQUESTED'


def test_mock_uart_selects_both_banks_and_checks_every_output(tmp_path, monkeypatch):
    source,trajectory=make_video_with_audio(tmp_path)
    # Test double simulates correctly selected audio/motion FIR ROM. It is NOT
    # a physical FPGA test and should never be described as COM-port evidence.
    import fpga_serial_client
    jobs=[]
    def fake_uart(port,values,job_id=1,baud=115200):
        assert port=='MOCK_PORT'
        jobs.append(job_id)
        return FirReference(design() if job_id&0x80 else None).process(values)
    monkeypatch.setattr(fpga_serial_client,'run_batch',fake_uart)
    result=run_unified_pipeline(source,trajectory,tmp_path/'mock',port='MOCK_PORT')
    assert 1 in jobs and 2 in jobs and 0x81 in jobs
    assert result.metrics['combined_hardware_verified']
    assert (result.output_dir/'final_stabilised_filtered_audio.mp4').exists()
    # The project metrics represent the algorithm's *mode*, but the mock
    # assertion is evidence of regression coverage ONLY, not real hardware.


def test_bad_audio_bank_never_reports_combined_hardware_pass(tmp_path,monkeypatch):
    source,trajectory=make_video_with_audio(tmp_path)
    import fpga_serial_client
    def wrong_bank(port,values,job_id=1,baud=115200):
        # Old bitstream's motion bank applied to audio incorrectly.
        return FirReference().process(values)
    monkeypatch.setattr(fpga_serial_client,'run_batch',wrong_bank)
    with pytest.raises(AssertionError,match='AUDIO FPGA mismatch'):
        run_unified_pipeline(source,trajectory,tmp_path/'fail',port='MOCK_PORT')
    assert not (tmp_path/'fail'/'combined_metrics.json').exists()


def test_short_aac_decode_is_padded_and_does_not_truncate_video(tmp_path, monkeypatch):
    """Simulate the 1,024-sample AAC shortfall seen on Windows FFmpeg."""
    source, trajectory = make_video_with_audio(tmp_path)
    import unified_pipeline
    actual_reader = unified_pipeline.read_audio

    def short_reader(*args, **kwargs):
        decoded = actual_reader(*args, **kwargs)
        return decoded[:FS-1024]

    monkeypatch.setattr(unified_pipeline, 'read_audio', short_reader)
    out = tmp_path/'aac_short_source'
    result = run_unified_pipeline(source, trajectory, out, port=None)
    audio = result.metrics['audio_filtering']
    assert audio['decoded_audio_samples'] == FS-1024
    assert audio['audio_end_silence_padding_samples'] == 1024
    assert audio['samples'] == FS
    with wave.open(str(out/'audio_filtered.wav'), 'rb') as f:
        assert f.getnframes() == FS
    before=cv2.VideoCapture(str(source))
    after=cv2.VideoCapture(str(out/'final_stabilised_filtered_audio.mp4'))
    assert before.get(cv2.CAP_PROP_FRAME_COUNT) == 30
    assert abs(before.get(cv2.CAP_PROP_FRAME_COUNT)-after.get(cv2.CAP_PROP_FRAME_COUNT)) <= 1
    before.release(); after.release()

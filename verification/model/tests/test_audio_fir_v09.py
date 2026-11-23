"""Audio v0.9 software/hardware-protocol tests. No physical FPGA claims."""
from __future__ import annotations
import sys
from pathlib import Path
import wave
import subprocess
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'host'))
from design_audio_coefficients import design, FS
from fixed_point_golden import FirReference
from audio_dsp import (AUDIO_JOB, BLOCK, MAX_JOB, analyze, filter_pcm,
                       process, reference_filter_pcm, write_pcm_wav)
from audio_preservation import _ffmpeg, source_has_audio


def _signal(n=16000):
    t = np.arange(n) / FS
    return np.clip(np.rint((.35*np.sin(2*np.pi*1000*t) +
                           .15*np.sin(2*np.pi*6000*t))*32767),-32768,32767).astype(np.int16)


def test_audio_coeffs_symmetric_unity_and_distinct_from_motion():
    c = design()
    assert len(c) == 17 and c == c[::-1] and sum(c) == (1<<15)
    assert max(c) <= 32767 and min(c) >= -32768
    from fixed_point_golden import load_coefficients
    assert c != load_coefficients()


def test_hiss_band_reduced_without_destroying_1khz_tone():
    x=_signal()
    y=reference_filter_pcm(x)
    m=analyze(x,y)
    assert m['high_band_5_7k5_attenuation_db'] < -30
    assert abs(m['speech_band_250_3000_change_db']) < 1.0


@pytest.mark.parametrize('size',[1,17,496,497,1029])
def test_hardware_batch_context_and_bit_exact(monkeypatch,size):
    import fpga_serial_client
    calls=[]
    def fake_batch(port, words, job_id):
        assert port == 'SIMULATED_PORT' and job_id == AUDIO_JOB
        assert 17 <= len(words) <= MAX_JOB
        calls.append(len(words))
        return FirReference(design()).process(words)
    monkeypatch.setattr(fpga_serial_client,'run_batch',fake_batch)
    x=_signal(size)
    actual,jobs=filter_pcm(x,'SIMULATED_PORT')
    assert np.array_equal(actual,reference_filter_pcm(x))
    assert jobs == (size+BLOCK-1)//BLOCK == len(calls)


def test_hardware_mismatch_refused(monkeypatch):
    import fpga_serial_client
    def fake_batch(port, words, job_id):
        return [0]*len(words)
    monkeypatch.setattr(fpga_serial_client,'run_batch',fake_batch)
    with pytest.raises(AssertionError,match='AUDIO FPGA mismatch'):
        filter_pcm(_signal(123),'TEST')


def test_wav_process_outputs_and_labels(tmp_path):
    s=_signal(1600)
    source=tmp_path/'input.wav'
    write_pcm_wav(source,s)
    result=process(source,tmp_path/'out',duration_s=.1)
    assert result['sample_rate_hz']==FS and result['samples']==1600
    assert result['hardware_verified'] is False and result['fpga_job_count']==0
    assert result['processing_mode'].startswith('SOFTWARE REFERENCE')
    for filename in ('audio_original.wav','audio_filtered.wav','audio_AB_compare.wav','audio_analysis.png','audio_metrics.json','AUDIO_RUN_REPORT.md'):
        assert (tmp_path/'out'/filename).stat().st_size > 100
    with wave.open(str(tmp_path/'out'/'audio_filtered.wav')) as wav:
        assert wav.getnframes()==1600 and wav.getframerate()==FS and wav.getnchannels()==1


def test_video_replaces_audio_but_not_frames(tmp_path):
    source=tmp_path/'source.mp4'
    r=subprocess.run([_ffmpeg(),'-hide_banner','-loglevel','error','-y',
        '-f','lavfi','-i','color=c=blue:s=160x90:r=30:d=0.5',
        '-f','lavfi','-i','sine=frequency=700:sample_rate=16000:duration=0.5',
        '-map','0:v:0','-map','1:a:0','-c:v','mpeg4','-q:v','5','-c:a','aac',
        '-shortest',str(source)],capture_output=True,text=True,timeout=60)
    if r.returncode:
        pytest.skip('ffmpeg build does not support lavfi synthetic media: '+r.stderr[-300:])
    assert source_has_audio(source)
    result=process(source,tmp_path/'out',duration_s=.45)
    assert result['video_with_filtered_audio']=='video_filtered_audio.mp4'
    assert source_has_audio(tmp_path/'out'/'video_filtered_audio.mp4')
    assert (tmp_path/'out'/'audio_AB_compare.wav').is_file()

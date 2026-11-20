"""Independent tests for the CPU-based environmental-noise suppression stage.

Synthetic noises are *controlled test signals*, not evidence of actual recorded
maritime speech quality. The FPGA verifies only the earlier FIR stage.
"""
from pathlib import Path
import sys
import wave
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from maritime_audio_enhancement import FS, suppress_maritime_noise
from audio_dsp import analyze
from unified_pipeline import AUDIO_CLEANUP_MODES, run_unified_pipeline
from test_unified_pipeline_v10 import make_video_with_audio


def test_preserves_sample_count_and_dtype_for_long_recording():
    rng=np.random.default_rng(11)
    source=rng.integers(-1300,1300,size=FS*5+51,dtype=np.int16)
    out, metrics=suppress_maritime_noise(source)
    assert len(out)==len(source) and out.dtype==np.int16
    assert metrics['stage'].startswith('HOST')
    assert not np.array_equal(out, source)


def test_never_invents_voice_for_silent_recording():
    sample=np.zeros(FS,dtype=np.int16)
    out, metrics=suppress_maritime_noise(sample)
    assert not np.any(out)
    assert metrics['note']=='Silent audio left unchanged'


def test_continuous_speech_tone_not_mistaken_for_stationary_noise():
    t=np.arange(FS,dtype=float)/FS
    original=(12000*np.sin(2*np.pi*700*t)).astype(np.int16)
    filtered, meta=suppress_maritime_noise(original)
    change=analyze(original,filtered)['speech_band_250_3000_change_db']
    assert abs(change) < 0.5, (change,meta)


def test_low_frequency_marine_rumble_is_attentuated():
    t=np.arange(FS*3,dtype=float)/FS
    # A controlled voice-like 600Hz tone with 90Hz engine hum.
    mixed=(6000*np.sin(2*np.pi*600*t) + 6000*np.sin(2*np.pi*90*t)).astype(np.int16)
    filtered, meta=suppress_maritime_noise(mixed)
    measure=analyze(mixed,filtered)
    assert measure['rumble_band_40_180_change_db'] < -10
    assert meta['quiet_frames']>0


def test_invalid_strength_and_stereo_inputs_rejected():
    with pytest.raises(ValueError, match='Strength'):
        suppress_maritime_noise(np.zeros(FS,dtype=np.int16),0.1)
    with pytest.raises(ValueError, match='mono'):
        suppress_maritime_noise(np.zeros((FS,2),dtype=np.int16))


def test_unified_sw_includes_two_independent_audio_stages(tmp_path):
    source,trajectory=make_video_with_audio(tmp_path)
    result=run_unified_pipeline(source, trajectory, tmp_path/'adaptive', port=None,
                                audio_cleanup='Maritime adaptive')
    a=result.metrics['audio_filtering']
    assert a['status']=='SOFTWARE REFERENCE ONLY'
    assert a['host_spectral_enhancement']['stage'].startswith('HOST')
    assert a['cleanup_mode']=='Maritime adaptive'
    assert result.metrics['final_media_fully_fpga_processed'] is False
    assert result.metrics['hybrid_host_audio_enhancement'] is True
    assert (result.output_dir/'audio_fir_only.wav').exists()
    with wave.open(str(result.output_dir/'audio_filtered.wav'),'rb') as f:
        assert f.getnframes()==FS
    basic=run_unified_pipeline(source, trajectory, tmp_path/'fir_only', port=None,
                               audio_cleanup='FIR only')
    assert basic.metrics['audio_filtering']['host_spectral_enhancement'] is None
    assert basic.metrics['hybrid_host_audio_enhancement'] is False


def test_gui_distinct_assessment_tabs_and_audio_stage_labels():
    tk=pytest.importorskip('tkinter')
    try:
        root=tk.Tk()
    except tk.TclError:
        pytest.skip('No available display')
    from maritime_gui import MaritimeGUI
    try:
        gui=MaritimeGUI(root)
        tabs=[gui.main_tabs.tab(i,'text') for i in range(gui.main_tabs.index('end'))]
        assert tabs==['Implementation','Video Assessment','Audio Assessment','Help']
        assert gui.audio_cleanup_mode.get()=='Maritime adaptive'
        gui.main_tabs.select(gui.audio_assessment_tab)
        root.update_idletasks()
        assert gui.audiocanvas.get_tk_widget().winfo_height()>100
    finally:
        root.destroy()

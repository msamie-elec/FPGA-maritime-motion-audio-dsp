"""RevG host-only process control and quality-report regressions.

No test here claims physical FPGA success. These tests exercise the actual
reference pipeline, GUI job flags, process termination, and cancellation
between complete serial transactions.
"""
from __future__ import annotations
import json
import sys
import threading
from pathlib import Path
import pytest
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from processing_control import checkpoint,ProcessingCancelled,run_process
from profile_comparison import compare_profiles
from gui_pipeline import run_pipeline
from generate_synthetic_clip import generate
from audio_dsp import filter_pcm


def test_cancel_before_processing_never_produces_verified_result(tmp_path):
    source,_=generate(tmp_path/'input',duration=2.0)
    cancel=threading.Event();cancel.set()
    with pytest.raises(ProcessingCancelled):
        run_pipeline(source,None,tmp_path/'output',None,cancel_event=cancel)
    assert not (tmp_path/'output'/'metrics.json').exists()


def test_software_profile_comparison_records_provenance_and_crop(tmp_path):
    source,_=generate(tmp_path/'input',duration=2.0)
    events=[]
    result=compare_profiles(source,None,tmp_path/'profile',progress=lambda *args:events.append(args))
    assert result['evidence_type']=='SOFTWARE_REFERENCE_PROFILE_COMPARISON_NOT_FPGA'
    assert len(result['input_sha256'])==64
    assert set(result['profiles'])=={'normal','strong'}
    assert 0 < result['profiles']['normal']['crop_area_retained_pct'] <= 100
    assert (tmp_path/'profile'/'profile_comparison.json').is_file()
    assert 'Independent image registration:' in (tmp_path/'profile'/'profile_comparison.md').read_text()
    assert isinstance(result['independent_image_proxy_favors_strong'], bool)
    assert events[0]==('profile_compare',0,2)
    assert events[-1]==('profile_compare',2,2)


def test_fpga_audio_cancellation_does_not_start_next_uart_job(monkeypatch):
    import fpga_serial_client
    from fixed_point_golden import FirReference
    from design_audio_coefficients import design
    ev=threading.Event()
    calls=[]
    def fake_batch(port, samples, job):
        calls.append(job)
        ev.set()  # Operator requests cancellation DURING this complete packet.
        return FirReference(design()).process(samples)
    monkeypatch.setattr(fpga_serial_client,'run_batch',fake_batch)
    with pytest.raises(ProcessingCancelled):
        filter_pcm(np.arange(1400,dtype=np.int16),'COM4',cancel_event=ev)
    assert calls==[0x81]


def test_cancellable_subprocess_stops_without_waiting_full_timeout():
    ev=threading.Event()
    out=run_process([sys.executable,'-c','print("done")'],cancel_event=ev,timeout=5,text=True)
    assert out.returncode==0 and out.stdout.strip()=='done'
    ev.set()
    with pytest.raises(ProcessingCancelled):
        run_process([sys.executable,'-c','import time;time.sleep(100)'],cancel_event=ev,timeout=120)


def test_gui_progress_and_request_cancel(monkeypatch):
    import tkinter as tk
    from maritime_gui import MaritimeGUI
    try:root=tk.Tk()
    except tk.TclError:
        pytest.skip('Requires a display')
    app=MaritimeGUI(root)
    try:
        event=threading.Event()
        app._cancel_event=event
        app._job_is_processing=True
        app._job_has_audio=True
        app._job_started=0.0
        app._set_busy(True)
        app._progress_ui('audio_fir',496,992)
        assert app.progress_pct.get() > 59
        app.request_cancel()
        assert event.is_set()
        assert 'Cancellation requested' in app.progress_label.get()
        assert 'disabled' in app.cancel_btn.state()
    finally:
        # Do not trigger an artificial serial cancellation in teardown.
        app._job_is_processing=False
        app._set_busy(False)
        app._release_video()
        root.destroy()

"""Playback regression: after processing both WAV choices must remain audible.

Test output-device command routing with fake PortAudio, NOT Windows speakers.
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from gui_audio_playback import PortAudioPlayer, SoundtrackPlayer
from test_gui_audio_playback_v102 import make_movie, write_wav, app


class FakePortAudio:
    def __init__(self): self.calls=[]
    def play(self, data, samplerate, blocking):
        self.calls.append(('play',len(data),samplerate,blocking,int(np.max(np.abs(data))) if len(data) else 0))
    def stop(self): self.calls.append(('stop',))


def test_portaudio_pcm16_offset_pause_resume_and_new_track(tmp_path):
    rate=16000
    a=(7000*np.sin(2*np.pi*440*np.arange(rate)/rate)).astype('<i2')
    b=(7000*np.sin(2*np.pi*950*np.arange(rate)/rate)).astype('<i2')
    for name,samples in [('original.wav',a),('filtered.wav',b)]:
        with wave.open(str(tmp_path/name),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
            f.writeframes(samples.tobytes())
    sd=FakePortAudio()
    dev=PortAudioPlayer(module=sd)
    dev.play(tmp_path/'original.wav',0)
    assert sd.calls[-1]==('play',rate,rate,False,7000)
    dev.play(tmp_path/'filtered.wav',0.5)
    assert sd.calls[-1][1:4]==(rate//2,rate,False)
    dev.stop()
    assert sd.calls[-1][0]=='stop'


def test_gui_original_then_filtered_then_original_after_processing(app,tmp_path):
    original=make_movie(tmp_path/'source.mp4',has_audio=True)
    pair=make_movie(tmp_path/'comparison.mp4',seconds=1.)
    out=tmp_path/'result';out.mkdir()
    # Generate *non-silent* original and filtered results, like pipeline exports.
    for name,freq in [('audio_original.wav',450),('audio_filtered.wav',550)]:
        samples=(5000*np.sin(2*np.pi*freq*np.arange(16000)/16000)).astype('<i2')
        with wave.open(str(out/name),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
            f.writeframes(samples.tobytes())

    app.source=original
    app._show_source_frame()
    app.toggle_play()
    assert app.soundtrack.last_playback['backend']=='MockAudio'
    app._pause_playback()
    # Simulate completion of unified pipeline and opening its comparison.
    app.result=SimpleNamespace(output_dir=out,side_by_side=pair)
    app._open_pair_video(pair)
    assert app.audio_choice.get()=='Filtered'
    app.toggle_play()
    assert app.soundtrack.last_playback['media'].endswith('audio_filtered.wav')
    app.audio_choice.set('Original')
    app._change_audio_choice()
    assert app.soundtrack.last_playback['media'].endswith('audio_original.wav')
    app._pause_playback()
    app._show_frame(app.frames-1)
    app.toggle_play()
    assert app.frame_idx==0
    assert app.soundtrack.last_playback['media'].endswith('audio_original.wav')
    app._pause_playback()
    app.audio_choice.set('Mute')
    app.toggle_play()
    assert app.soundtrack.last_playback['media'].endswith('audio_original.wav')
    app._pause_playback()


def test_gui_postprocess_playback_errors_are_visible(app,tmp_path):
    source=make_movie(tmp_path/'source.mp4')
    out=tmp_path/'result';out.mkdir()
    write_wav(out/'audio_filtered.wav')
    app.source=source
    app.result=SimpleNamespace(output_dir=out,side_by_side=source)
    app._open_pair_video(source)
    def fail(*a,**k):raise RuntimeError('SPEAKER DEVICE ERROR')
    app.soundtrack.play=fail
    app.toggle_play()
    assert 'SPEAKER DEVICE ERROR' in app.status.get()
    app._pause_playback()

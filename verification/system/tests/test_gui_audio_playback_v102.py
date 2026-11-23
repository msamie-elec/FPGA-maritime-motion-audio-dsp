"""Host-only audio/video sync checks. Fake audio device != physical sound test."""
from __future__ import annotations
import sys
from pathlib import Path
import subprocess
import wave
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
import tkinter as tk

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'host'))
from audio_preservation import _ffmpeg
from gui_audio_playback import SoundtrackPlayer
from maritime_gui import MaritimeGUI


class MockAudio:
    def __init__(self): self.calls=[]
    def play(self, wav, pos): self.calls.append(('play',Path(wav),round(pos,3)))
    def stop(self): self.calls.append(('stop',))


def write_wav(path, secs=1.0):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(np.zeros(round(secs*16000),dtype='<i2').tobytes())
    return path


def make_movie(path, seconds=1., has_audio=False):
    fps=30
    w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(160,90))
    assert w.isOpened()
    for i in range(round(fps*seconds)):
        img=np.full((90,160,3),i*5%255,dtype=np.uint8)
        w.write(img)
    w.release()
    if has_audio:
        wav=write_wav(path.parent/'beep.wav',seconds)
        new=path.parent/'merged.mp4'
        r=subprocess.run([_ffmpeg(),'-loglevel','error','-y','-i',str(path),'-i',str(wav),'-map','0:v:0', '-map','1:a:0', '-c:v','copy','-c:a','aac','-shortest',str(new)],capture_output=True,text=True,timeout=30)
        assert r.returncode==0,r.stderr
        new.replace(path)
    return path


def test_extract_mp4_audio_once_and_support_replay(tmp_path):
    source=make_movie(tmp_path/'clip.mp4',has_audio=True)
    mock=MockAudio()
    player=SoundtrackPlayer(backend=mock,cache_dir=tmp_path/'cache')
    assert player.supported
    prepared=player.wav_for(source)
    assert prepared.exists() and prepared.suffix=='.wav'
    assert player.wav_for(source)==prepared
    with wave.open(str(prepared),'rb') as f:
        assert f.getframerate()==16000 and f.getnchannels()==1
    assert player.play(source,0.0)
    assert player.play(source,.5)
    player.stop()
    assert [x[0] for x in mock.calls].count('play')==2
    assert [x[2] for x in mock.calls if x[0]=='play']==[0.0,0.5]
    player.close()


@pytest.fixture
def app(tmp_path):
    try: root=tk.Tk()
    except tk.TclError: pytest.skip('Desktop display required')
    gui=MaritimeGUI(root)
    # Independent fake output device; assertions verify call ordering only.
    gui.soundtrack.close()
    gui._fake_audio=MockAudio()
    gui.soundtrack=SoundtrackPlayer(backend=gui._fake_audio,cache_dir=tmp_path/'cache')
    root.update()
    try:yield gui
    finally:
        gui._release_video();gui.soundtrack.close()
        try:root.destroy()
        except tk.TclError:pass


def test_original_audio_plays_before_processing_and_stops_on_pause(app,tmp_path,monkeypatch):
    path=make_movie(tmp_path/'ship.mp4',has_audio=True)
    monkeypatch.setattr('maritime_gui.filedialog.askopenfilename',lambda **k:str(path))
    app.choose_video()
    assert app.result is None and app.audio_choice.get()=='Original'
    app.toggle_play()
    plays=[x for x in app._fake_audio.calls if x[0]=='play']
    assert len(plays)==1 and plays[0][2]==0.0
    assert plays[0][1].suffix=='.wav'
    app.toggle_play()
    assert app._fake_audio.calls[-1][0]=='stop'
    app._show_frame(15)
    app.toggle_play()
    plays=[x for x in app._fake_audio.calls if x[0]=='play']
    assert len(plays)==2 and plays[-1][2]==pytest.approx(.5)
    app._pause_playback()
    app.audio_choice.set('Mute')
    app.toggle_play()
    assert len([x for x in app._fake_audio.calls if x[0]=='play'])==2


def test_processed_player_defaults_filtered_and_select_original(app,tmp_path):
    media=make_movie(tmp_path/'pair.mp4')
    out=tmp_path/'result';out.mkdir()
    write_wav(out/'audio_original.wav')
    write_wav(out/'audio_filtered.wav')
    app.source=media
    app.result=SimpleNamespace(output_dir=out,side_by_side=media)
    app._open_pair_video(media)
    assert app.audio_choice.get()=='Filtered'
    app.toggle_play()
    assert [x for x in app._fake_audio.calls if x[0]=='play'][-1][1].name=='audio_filtered.wav'
    app.audio_choice.set('Original')
    app._change_audio_choice()
    assert [x for x in app._fake_audio.calls if x[0]=='play'][-1][1].name=='audio_original.wav'
    app._pause_playback()
    app._show_frame(app.frames-1)
    app.toggle_play()
    assert app.frame_idx==0 and app.playing
    app._pause_playback()


def test_video_follows_elapsed_time_not_timer_count(app,tmp_path,monkeypatch):
    media=make_movie(tmp_path/'v.mp4')
    app.source=media
    app._show_source_frame()
    app.audio_choice.set('Mute')
    app.toggle_play()
    app._play_start-=0.55
    app._cancel_play_timer();app._play_tick()
    assert app.frame_idx>=16, 'Delayed redraw must skip frames to catch up to audio time'
    app._pause_playback()

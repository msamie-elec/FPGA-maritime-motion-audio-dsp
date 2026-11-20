"""Mock FPGA long-video packet overlap and audio-preservation tests."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import numpy as np
import pytest
from fixed_point_golden import FirReference,centered_smooth
import stabilize_video

@pytest.mark.parametrize('n',[18,149,496,497,906,1500])
def test_long_packet_overlap(monkeypatch,n):
    import fpga_serial_client
    calls=[]
    def mock_batch(port,samples,job_id):
        assert port=='MOCK' and job_id==3 and len(samples)<=512
        calls.append(len(samples))
        return FirReference().process(samples)
    monkeypatch.setattr(fpga_serial_client,'run_batch',mock_batch)
    source=[int(14000*np.sin(i*.2)+3000*np.cos(i*.13)) for i in range(n)]
    assert stabilize_video.smooth_trajectory(source,'MOCK',3)==centered_smooth(source)
    assert len(calls)==(n+495)//496

def test_long_video_input_supported(tmp_path):
    import cv2
    from motion_estimation import inspect_video
    clip=tmp_path/'long.mp4'
    writer=cv2.VideoWriter(str(clip),cv2.VideoWriter_fourcc(*'mp4v'),30,(96,72))
    assert writer.isOpened()
    for i in range(520):
        frame=np.zeros((72,96,3),dtype=np.uint8)
        frame[12:30,(i//3)%60:(i//3)%60+20]=255
        writer.write(frame)
    writer.release()
    assert inspect_video(clip).frames==520

def test_audio_preserved(tmp_path):
    import cv2,subprocess
    from audio_preservation import _ffmpeg,source_has_audio,mux_original_audio
    raw=tmp_path/'source.m4a'
    r=subprocess.run([_ffmpeg(),'-loglevel','error','-y','-f','lavfi','-i',
                      'sine=frequency=440:duration=1','-c:a','aac',str(raw)],capture_output=True)
    if r.returncode:pytest.skip('FFmpeg lavfi sine unavailable')
    video=tmp_path/'out.mp4'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),30,(96,72))
    assert writer.isOpened()
    for _ in range(30):writer.write(np.zeros((72,96,3),dtype=np.uint8))
    writer.release()
    assert source_has_audio(raw)
    assert mux_original_audio(video,raw)['audio_preserved']
    assert source_has_audio(video)

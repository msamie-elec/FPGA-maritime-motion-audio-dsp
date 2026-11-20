"""Original soundtrack preservation for exported MP4; NO audio noise reduction."""
from pathlib import Path
import subprocess, os

def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError('Install imageio-ffmpeg from host/requirements.txt') from exc

def source_has_audio(source: Path) -> bool:
    result=subprocess.run([_ffmpeg(),'-hide_banner','-i',str(source)],
                          capture_output=True,text=True,timeout=30)
    return 'Audio:' in result.stderr

def mux_original_audio(silent_video: Path, source: Path, start_s: float=0.0) -> dict:
    silent_video,source=Path(silent_video),Path(source)
    if not source_has_audio(source):
        return {'audio_present':False,'audio_preserved':False,'description':'No source audio stream'}
    tmp=silent_video.with_name(silent_video.stem+'_with_audio_tmp.mp4')
    cmd=[_ffmpeg(),'-hide_banner','-loglevel','error','-y','-i',str(silent_video),
         '-ss',f'{start_s:.6f}','-i',str(source),'-map','0:v:0','-map','1:a:0',
         '-c:v','copy','-c:a','aac','-b:a','128k','-shortest',str(tmp)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if result.returncode or not tmp.exists() or tmp.stat().st_size==0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError('Could not preserve source audio: '+result.stderr[-500:])
    os.replace(tmp,silent_video)
    return {'audio_present':True,'audio_preserved':True,'description':'Original AAC soundtrack retained; not noise filtered'}

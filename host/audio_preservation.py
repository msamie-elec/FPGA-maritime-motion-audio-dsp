"""Preserve the source soundtrack in video exports; do not filter audio yet.

Tkinter/OpenCV's in-app frames have no audio playback. The exported MP4
does preserve its audio, and can be played in a media player. Audio remains
unaltered, for the next planned DSP audio-noise project milestone.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import os
from processing_control import checkpoint, run_process, ProcessingCancelled

def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("Audio preservation needs imageio-ffmpeg (pip install -r host/requirements.txt)") from e


def source_has_audio(source: Path) -> bool:
    ffmpeg = _ffmpeg()
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", str(source)],
                          text=True, capture_output=True, timeout=30)
    return "Audio:" in proc.stderr


def mux_original_audio(silent_video: Path, source: Path, start_s: float = 0.0, *, cancel_event=None) -> dict:
    """Replace video atomically with its exact same frames plus source AAC audio.

    Audio is copied from the original for timing/content, then AAC encoded.
    Returns metadata, never claims audio noise filtering has been performed.
    """
    silent_video, source = Path(silent_video), Path(source)
    checkpoint(cancel_event)
    if not source_has_audio(source):
        return {'audio_present': False, 'audio_preserved': False,
                'description': 'Source contains no audio stream'}
    tmp = silent_video.with_name(silent_video.stem + "_with_audio_tmp.mp4")
    ffmpeg = _ffmpeg()
    args = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(silent_video), '-ss', f'{start_s:.6f}', '-i', str(source),
            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k', '-shortest', str(tmp)]
    try:
        result = run_process(args, cancel_event=cancel_event, text=True, timeout=180)
    except (ProcessingCancelled, subprocess.TimeoutExpired):
        tmp.unlink(missing_ok=True)
        raise
    if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Failed to retain source audio in the stabilised MP4: " + result.stderr[-500:])
    os.replace(tmp, silent_video)
    return {'audio_present': True, 'audio_preserved': True,
            'description': 'Original source audio retained in exported MP4 (AAC); not noise filtered'}

"""Synchronised soundtrack playback for the Windows Tk video GUI.

Use PortAudio (sounddevice) for reliable PCM playback on Windows. MCI is kept
as a fallback if PortAudio is unavailable or reports a device error. FFmpeg
converts MP4/AAC once to 16-kHz, mono, signed 16-bit PCM WAV. A monotonic
clock in MaritimeGUI drives video frames from the same presentation time.

The FPGA does NOT stream audio in real time: playback is of completed files.
Linux/macOS fall back to the external-player button, explicitly not silently
pretending that sound is supported in the embedded viewer.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

import numpy as np

from audio_preservation import _ffmpeg


class PortAudioPlayer:
    """Sound-device PCM playback. Reopening from a sample offset works for WAV.

    sounddevice manages a PortAudio output stream asynchronously, independently
    from Tk. Never play from a Tk redraw callback or on the processing worker.
    """
    def __init__(self, module=None):
        if module is None:
            import sounddevice as module
        self.sd = module

    def play(self, wav: Path, offset_seconds: float) -> None:
        self.stop()
        with wave.open(str(wav), 'rb') as fp:
            if fp.getsampwidth() != 2 or fp.getnchannels() != 1:
                raise ValueError('Expected mono PCM16 WAV for playback')
            rate = fp.getframerate()
            if rate <= 0:
                raise ValueError('Invalid WAV sample rate')
            frame_count = fp.getnframes()
            start = max(0, min(frame_count, round(float(offset_seconds) * rate)))
            fp.setpos(start)
            buf = fp.readframes(frame_count - start)
        if not buf:
            return
        samples = np.frombuffer(buf, dtype='<i2').copy()
        # Do not block the GUI during audio playback. PortAudio handles
        # int16 conversion and delivery to the selected Windows speaker.
        self.sd.play(samples, samplerate=rate, blocking=False)

    def stop(self) -> None:
        self.sd.stop()


class WindowsMCI:
    """MCI waveaudio controller. Only instantiated on Windows."""
    def __init__(self):
        import ctypes
        self._ctypes = ctypes
        self._dll = ctypes.WinDLL('winmm')
        self._send = self._dll.mciSendStringW
        self._send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                               ctypes.c_uint, ctypes.c_void_p]
        self._send.restype = ctypes.c_uint
        self._error_text = self._dll.mciGetErrorStringW
        self._error_text.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        self._error_text.restype = ctypes.c_bool
        self.alias = 'maritime_gui_pcm_audio'
        self.active = False

    def _command(self, text: str) -> None:
        err = self._send(text, None, 0, None)
        if err:
            buffer = self._ctypes.create_unicode_buffer(512)
            self._error_text(err, buffer, len(buffer))
            raise RuntimeError(f'Windows audio playback error {err}: {buffer.value}')

    def play(self, wav: Path, offset_seconds: float) -> None:
        self.stop()
        # MCI supports ordinary PCM WAV on Windows. Quote paths with spaces.
        # A double quote in a filename cannot be represented in MCI syntax.
        if '"' in str(wav):
            raise ValueError('Unsupported double quote in audio filename')
        self._command(f'open "{wav}" type waveaudio alias {self.alias}')
        self.active = True
        try:
            self._command(f'set {self.alias} time format milliseconds')
            self._command(f'play {self.alias} from {max(0, round(offset_seconds * 1000))}')
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if self.active:
            try:
                self._command(f'stop {self.alias}')
            finally:
                try:
                    self._command(f'close {self.alias}')
                finally:
                    self.active = False


class SoundtrackPlayer:
    """Prepare original or filtered audio and play it from a video timestamp."""
    def __init__(self, backend=None, cache_dir: Path | None = None):
        self._temp = None
        if cache_dir is None:
            self._temp = tempfile.TemporaryDirectory(prefix='maritime_gui_audio_')
            cache_dir = Path(self._temp.name)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fallback = None
        if backend is not None:
            self.backend = backend
        elif sys.platform == 'win32':
            # Use PortAudio first; MCI still works if sounddevice is unavailable.
            try:
                self.backend = PortAudioPlayer()
                self.fallback = WindowsMCI()
            except (ImportError, OSError):
                self.backend = WindowsMCI()
        else:
            self.backend = None
        self.last_playback: dict[str, object] | None = None
        self._cache: dict[tuple[str,int,int], Path] = {}

    @property
    def supported(self) -> bool:
        return self.backend is not None

    def wav_for(self, media: Path) -> Path:
        media = Path(media).resolve()
        if not media.exists():
            raise FileNotFoundError(f'Audio media not found: {media}')
        if media.suffix.lower() == '.wav':
            return media
        stat = media.stat()
        key = (str(media), stat.st_size, stat.st_mtime_ns)
        cached = self._cache.get(key)
        if cached is not None and cached.exists():
            return cached
        digest = hashlib.sha256(repr(key).encode('utf-8')).hexdigest()[:18]
        output = self.cache_dir / (digest + '.wav')
        cmd = [_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(media), '-map', '0:a:0', '-vn', '-ac', '1',
               '-ar', '16000', '-c:a', 'pcm_s16le', str(output)]
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        if res.returncode or not output.is_file() or output.stat().st_size < 44:
            output.unlink(missing_ok=True)
            raise RuntimeError('Cannot decode soundtrack: ' + res.stderr[-400:])
        self._cache[key] = output
        return output

    def play(self, media: Path, offset_seconds: float = 0.0) -> bool:
        if not self.supported:
            return False
        wav = self.wav_for(media)
        try:
            self.backend.play(wav, offset_seconds)
        except Exception as primary_exc:
            # Never silently drop post-processing audio: try Windows MCI, and
            # if both fail, show BOTH errors in the GUI log/status.
            if self.fallback is None:
                raise
            try:
                self.fallback.play(wav, offset_seconds)
                self.backend, self.fallback = self.fallback, None
            except Exception as fallback_exc:
                raise RuntimeError(
                    f'PortAudio playback failed: {primary_exc}; '
                    f'MCI fallback failed: {fallback_exc}') from fallback_exc
        with wave.open(str(wav), 'rb') as fp:
            frames, rate = fp.getnframes(), fp.getframerate()
        self.last_playback = {
            'media': str(Path(media)), 'wav': str(wav),
            'backend': type(self.backend).__name__,
            'duration_s': round(frames/rate, 3),
            'start_s': round(offset_seconds, 3),
        }
        return True

    def stop(self) -> None:
        if self.supported:
            self.backend.stop()
        if self.fallback is not None:
            self.fallback.stop()

    def close(self) -> None:
        self.stop()
        if self._temp is not None:
            self._temp.cleanup()

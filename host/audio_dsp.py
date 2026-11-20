"""Offline speech-band FIR audio prototype, software or verified Arty A7.

Source MP4/WAV -> ffmpeg PCM16 mono 16 kHz -> signed 24-bit Q16.8 samples
-> 17-tap AUDIO ROM -> WAV and optional video excerpt with cleaned soundtrack.

No live audio / mic, no unverified 'FPGA' fallback, no neural denoising.
The 3.2 kHz lowpass targets hiss outside the principal speech band; it can
also remove genuine high-frequency vocal consonants or leave in-band noise.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from audio_preservation import _ffmpeg
from design_audio_coefficients import design, FS
from fixed_point_golden import FirReference, centered_smooth

AUDIO_JOB = 0x81  # high job-ID bit selects audio coefficients in v0.9 FPGA RTL
MAX_JOB = 512
BLOCK = MAX_JOB - 16
MAX_SECONDS = 50.5  # accommodates the full supported 1500-frame / 30-fps video


def read_audio(source: Path, start_s: float = 0.0, duration_s: float = 4.0) -> np.ndarray:
    """Extract exact 16 kHz mono signed PCM16 via ffmpeg, with input untouched."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not (0 <= start_s <= 3600 and 0 < duration_s <= MAX_SECONDS):
        raise ValueError(f'start >= 0, duration 0..{MAX_SECONDS}s required')
    args = [_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-ss', f'{start_s:.6f}',
            '-i', str(source), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(FS),
            '-t', f'{duration_s:.6f}', '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1']
    r = subprocess.run(args, capture_output=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError('Cannot decode source audio (or source has no audio): ' +
                           r.stderr.decode('utf-8', 'replace')[-450:])
    if not r.stdout or len(r.stdout) % 2:
        raise ValueError('Source has no usable audio in the selected segment')
    return np.frombuffer(r.stdout, dtype='<i2').copy()


def write_pcm_wav(path: Path, values: np.ndarray) -> None:
    values = np.asarray(values, dtype=np.int16)
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(FS)
        f.writeframes(values.astype('<i2').tobytes())


def reference_filter_pcm(samples: np.ndarray) -> np.ndarray:
    """Bit-exact centered 17-tap audio FIR, using the actual fixed-point model."""
    raw = np.asarray(samples, dtype=np.int16)
    if len(raw) == 0:
        return raw.copy()
    q = [int(x) << 8 for x in raw]
    f = centered_smooth(q, design())
    return np.clip(np.asarray(f, dtype=np.int64) >> 8, -32768, 32767).astype(np.int16)


def filter_pcm(samples: np.ndarray, port: str | None = None) -> tuple[np.ndarray, int]:
    raw = np.asarray(samples, dtype=np.int16)
    if len(raw) == 0:
        raise ValueError('Empty audio segment')
    original_q = [int(x) << 8 for x in raw]
    expected_q = centered_smooth(original_q, design())
    if port is None:
        filtered_q = expected_q
        jobs = 0
    else:
        # Keep all hardware samples backed by an authentic serial response.
        from fpga_serial_client import run_batch
        filtered_q, jobs = [], 0
        for start in range(0, len(original_q), BLOCK):
            fragment = original_q[start:start+BLOCK]
            left = [original_q[max(0, i)] for i in range(start-8, start)]
            right = [original_q[min(len(original_q)-1, i)]
                     for i in range(start+len(fragment), start+len(fragment)+8)]
            padded = left + fragment + right
            if not 17 <= len(padded) <= MAX_JOB:
                raise AssertionError('Unexpected UART overlap size')
            received = run_batch(port, padded, AUDIO_JOB)
            actual = received[16:16+len(fragment)]
            expected = expected_q[start:start+len(fragment)]
            if len(actual) != len(fragment) or actual != expected:
                raise AssertionError('AUDIO FPGA mismatch at sample %d — no hardware verification' % start)
            jobs += 1
            filtered_q.extend(actual)
    result = np.clip(np.asarray(filtered_q, dtype=np.int64) >> 8, -32768, 32767).astype(np.int16)
    return result, jobs


def _band_power(samples: np.ndarray, low: float, high: float) -> float:
    a = np.asarray(samples, dtype=np.float64)
    n = len(a)
    if n < 64:
        return 0.0
    a = a - np.mean(a)
    window = np.hanning(n)
    spectrum = np.fft.rfft(a * window)
    freqs = np.fft.rfftfreq(n, d=1/FS)
    mask = (freqs >= low) & (freqs <= high)
    return float(np.sum(np.abs(spectrum[mask])**2))


def analyze(original: np.ndarray, filtered: np.ndarray) -> dict:
    if len(original) != len(filtered):
        raise ValueError('Audio original/filtered sample mismatch')
    high_before = _band_power(original, 5000, 7500)
    high_after = _band_power(filtered, 5000, 7500)
    low_before = _band_power(original, 40, 180)
    low_after = _band_power(filtered, 40, 180)
    speech_before = _band_power(original, 250, 3000)
    speech_after = _band_power(filtered, 250, 3000)
    def change_db(after: float, before: float) -> float | None:
        if before <= 1e-12:
            return None
        return round(10*math.log10(max(after, 1e-15)/before), 2)
    return {
        'high_band_5_7k5_attenuation_db': change_db(high_after, high_before),
        'rumble_band_40_180_change_db': change_db(low_after, low_before),
        'speech_band_250_3000_change_db': change_db(speech_after, speech_before),
        'note': 'Spectral-band attenuation, NOT a measured improvement in intelligibility or isolated noise suppression.',
    }


def plot_audio(original: np.ndarray, filtered: np.ndarray, out: Path) -> None:
    n = len(original)
    fig = Figure(figsize=(12, 7.5), dpi=125)
    FigureCanvasAgg(fig)
    ax1, ax2 = fig.subplots(2, 1)
    every = max(1, n // 2500)
    t = np.arange(n)/FS
    ax1.plot(t[::every], original[::every], lw=.75, alpha=.65, label='Original PCM')
    ax1.plot(t[::every], filtered[::every], lw=.8, alpha=.8, label='Speech-band FIR')
    ax1.set(title='Audio waveform (16 kHz mono)', xlabel='Time (s)', ylabel='PCM16 amplitude')
    ax1.grid(alpha=.22); ax1.legend()
    def spec(y: np.ndarray):
        frame = np.asarray(y, dtype=np.float64)
        f = np.fft.rfftfreq(len(frame), 1/FS)
        a = np.abs(np.fft.rfft((frame-frame.mean())*np.hanning(len(frame))))
        return f, 20*np.log10(np.maximum(a, 1e-9))
    f, a = spec(original); _, b = spec(filtered)
    ax2.plot(f, a, alpha=.75, label='Original')
    ax2.plot(f, b, alpha=.9, label='Filtered')
    ax2.axvline(3200, ls='--', alpha=.55, label='3.2 kHz nominal cutoff')
    ax2.set(xlim=(0, FS//2),title='Frequency spectrum', xlabel='Frequency (Hz)', ylabel='Relative magnitude (dB)')
    ax2.grid(alpha=.22);ax2.legend()
    fig.subplots_adjust(hspace=.37, left=.08, right=.97, bottom=.08, top=.94)
    fig.savefig(out)


def mux_audio_into_excerpt(source: Path, wav: Path, path: Path,
                            start_s: float, duration_s: float) -> bool:
    if source.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.mkv', '.avi'):
        return False
    cmd = [_ffmpeg(), '-hide_banner','-loglevel','error','-y',
           '-ss', f'{start_s:.6f}', '-i',str(source), '-i',str(wav),
           '-map','0:v:0','-map','1:a:0','-t',f'{duration_s:.6f}',
           '-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac',
           '-b:a','128k','-shortest',str(path)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if r.returncode or not path.is_file():
        raise RuntimeError('Failed to export cleaned soundtrack/video excerpt: ' + r.stderr[-500:])
    return True


def process(source: Path, out_dir: Path, *, port: str | None = None,
            start_s: float = 0.0, duration_s: float = 4.0) -> dict:
    t0=time.perf_counter()
    source=Path(source);out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    raw=read_audio(source,start_s,duration_s)
    filtered,jobs=filter_pcm(raw,port)
    a=out_dir/'audio_original.wav'; b=out_dir/'audio_filtered.wav'
    write_pcm_wav(a,raw);write_pcm_wav(b,filtered)
    # A/B listening: source first, then processed, separated by 350 ms silence.
    gap = np.zeros(round(.35*FS),dtype=np.int16)
    write_pcm_wav(out_dir/'audio_AB_compare.wav',np.concatenate([raw,gap,filtered]))
    plot_audio(raw,filtered,out_dir/'audio_analysis.png')
    actual_duration=len(raw)/FS
    mp4=out_dir/'video_filtered_audio.mp4'
    exported=mux_audio_into_excerpt(source,b,mp4,start_s,actual_duration)
    metrics={
        'processing_mode': 'PHYSICAL FPGA — BIT EXACT AGAINST PYTHON' if port else 'SOFTWARE REFERENCE — NO FPGA',
        'source': source.name,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'sample_rate_hz':FS,'channels':1,'sample_format':'signed PCM16; Q16.8 on FPGA UART',
        'audio_bank':'17-tap Hamming low-pass 3200 Hz @16kHz',
        'samples':len(raw),'duration_s':round(actual_duration,3),
        'physical_port':port,'fpga_job_count':jobs,'hardware_verified':port is not None,
        'video_with_filtered_audio':mp4.name if exported else None,
        'end_to_end_s':round(time.perf_counter()-t0,3),
        'analysis':analyze(raw,filtered),
        'limitations':'Offline, mono speech-band low-pass only. Cannot remove overlapping in-band engine/wind noise or recover masked speech.',
    }
    (out_dir/'audio_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
    (out_dir/'AUDIO_RUN_REPORT.md').write_text(
        '# Audio FIR assessment\n\n**Mode:** '+metrics['processing_mode']+'\n\n'+
        '**Source:** '+metrics['source']+'\n\n'+
        f"**Duration:** {actual_duration:.3f} s; 16 kHz mono; {len(raw)} samples\n\n"+
        f"**High-band 5–7.5 kHz change:** {metrics['analysis']['high_band_5_7k5_attenuation_db']} dB\n\n"+
        f"**Speech-band 0.25–3 kHz change:** {metrics['analysis']['speech_band_250_3000_change_db']} dB\n\n"+
        'Band-power changes alone do not establish speech intelligibility or voice quality.\n',
        encoding='utf-8')
    return metrics


def main():
    ap=argparse.ArgumentParser(description='Offline FPGA-compatible 16kHz speech-band FIR audio filter')
    ap.add_argument('--source',type=Path,required=True,help='MP4, WAV or other ffmpeg-decodable media with audio')
    ap.add_argument('--out',type=Path,default=Path('videos/sim/audio_demo'))
    ap.add_argument('--port',help='Physical Arty UART port, requires NEW v0.9 FPGA bitstream')
    ap.add_argument('--start',type=float,default=0.0)
    ap.add_argument('--seconds',type=float,default=4.0)
    args=ap.parse_args()
    result=process(args.source,args.out,port=args.port,start_s=args.start,duration_s=args.seconds)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

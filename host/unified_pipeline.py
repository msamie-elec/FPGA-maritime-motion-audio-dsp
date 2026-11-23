"""One-source maritime FPGA video + audio pipeline (development v1.0).

Video stabilization and audio noise reduction are independent, audited DSP
operations feeding ONE final MP4. Video remains host-warped after FPGA FIR
trajectory processing; audio is decoded/encoded by FFmpeg after optional FPGA
FIR speech-band processing. No live audio/video FPGA streaming is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np

from audio_preservation import _ffmpeg, source_has_audio
from audio_dsp import (FS, analyze, filter_pcm, plot_audio, read_audio,
                       write_pcm_wav)
from gui_pipeline import ProcessingResult, run_pipeline
from maritime_audio_enhancement import suppress_maritime_noise
from motion_estimation import inspect_video
from processing_control import checkpoint, progress as notify, run_process, ProcessingCancelled

PROCESSING_MODES = ('Video + Audio', 'Video only')
AUDIO_CLEANUP_MODES = ('Maritime adaptive', 'FIR only')


def _run_ffmpeg(args: list[str], output: Path, *, timeout: int = 240, cancel_event=None) -> None:
    try:
        proc = run_process([_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
                            *args, str(output)], cancel_event=cancel_event,
                           text=True, timeout=timeout)
    except (ProcessingCancelled,subprocess.TimeoutExpired):
        output.unlink(missing_ok=True)
        raise
    if proc.returncode or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise RuntimeError('FFmpeg final media export failed: ' + proc.stderr[-700:])


def replace_soundtrack(mp4: Path, wav: Path, *, cancel_event=None) -> None:
    """Atomically replace audio without touching encoded video frames."""
    mp4, wav = Path(mp4), Path(wav)
    temporary = mp4.with_name(mp4.stem + '.new_audio.mp4')
    try:
        _run_ffmpeg(['-i', str(mp4), '-i', str(wav), '-map', '0:v:0',
                     '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
                     '-b:a', '160k', '-shortest', '-movflags', '+faststart'], temporary,cancel_event=cancel_event)
        os.replace(temporary, mp4)
    finally:
        temporary.unlink(missing_ok=True)


def write_finished_video(comparison: Path, final: Path, *, cancel_event=None) -> None:
    """Export only right-hand stabilised half with its cleaned AAC audio."""
    _run_ffmpeg(['-i', str(comparison), '-map', '0:v:0', '-map', '0:a:0',
                 '-vf', 'crop=iw/2:ih:iw/2:0', '-c:v', 'libx264', '-preset',
                 'veryfast', '-crf', '22', '-c:a', 'copy', '-movflags', '+faststart'],
                final, timeout=300,cancel_event=cancel_event)


def run_unified_pipeline(video: Path, trajectory: Path | None, output_dir: Path,
                         port: str | None, profile: str = 'Normal',
                         processing: str = 'Video + Audio',
                         audio_cleanup: str = 'Maritime adaptive', *, cancel_event=None, progress=None) -> ProcessingResult:
    """Process both channels, requiring independently verifiable FPGA outputs.

    'Video only' retains the previous video stabilisation behaviour and original
    soundtrack. 'Video + Audio' requires a real audio track and the new v0.9+
    hardware coefficient-bank bitstream if port is provided. Failure never
    changes hardware_verified to True or emits a successful combined report.
    """
    if processing not in PROCESSING_MODES:
        raise ValueError(f'Processing must be one of {PROCESSING_MODES!r}')
    if audio_cleanup not in AUDIO_CLEANUP_MODES:
        raise ValueError(f'Audio cleanup must be one of {AUDIO_CLEANUP_MODES!r}')
    source = Path(video)
    info = inspect_video(source)
    if processing == 'Video + Audio' and not source_has_audio(source):
        raise ValueError('This video has no audio track. Choose Video only, or load a video with sound.')
    dest = Path(output_dir)
    started = time.perf_counter()
    result = run_pipeline(source, trajectory, dest, port, profile=profile, cancel_event=cancel_event, progress=progress)
    checkpoint(cancel_event)
    metrics = result.metrics
    metrics['combined_processing'] = processing
    metrics['audio_filtering'] = {'status': 'NOT REQUESTED', 'hardware_verified': False}
    if processing == 'Video only':
        (dest/'metrics.json').write_text(json.dumps(metrics, indent=2)+'\n', encoding='utf-8')
        return result

    # The processed source has the same frame clock as the original, so the
    # first sample is t=0. Encode only the decoded frames' time interval.
    seconds = info.frames / info.fps
    notify(progress,'audio_decode',0,1)
    checkpoint(cancel_event)
    decoded_audio = read_audio(source, start_s=0.0, duration_s=seconds, cancel_event=cancel_event)
    checkpoint(cancel_event)
    notify(progress,'audio_decode',1,1)
    # AAC encoder priming / end-of-stream packet boundaries differ between
    # FFmpeg builds. Some Windows builds decode 14,976 rather than 16,000
    # samples for an otherwise one-second AAC fixture (one 1,024-sample
    # packet short). Match the exact decoded-video frame interval instead
    # of permitting '-shortest' to silently truncate video frames.
    expected_samples = round(seconds * FS)
    missing_samples = max(0, expected_samples - len(decoded_audio))
    trimmed_samples = max(0, len(decoded_audio) - expected_samples)
    if missing_samples:
        raw = np.pad(decoded_audio, (0, missing_samples), mode='constant')
    else:
        raw = decoded_audio[:expected_samples].copy()
    fir_cleaned, jobs = filter_pcm(raw, port, cancel_event=cancel_event, progress=progress)
    checkpoint(cancel_event)
    notify(progress,'audio_enhancement',0,1)
    if audio_cleanup == 'Maritime adaptive':
        cleaned, host_enhancement = suppress_maritime_noise(fir_cleaned)
    else:
        cleaned, host_enhancement = fir_cleaned.copy(), None
    checkpoint(cancel_event)
    notify(progress,'audio_enhancement',1,1)
    if len(cleaned) != len(raw):
        raise AssertionError('Audio DSP output length differs from input')
    write_pcm_wav(dest/'audio_original.wav', raw)
    write_pcm_wav(dest/'audio_fir_only.wav', fir_cleaned)
    cleaned_wav = dest/'audio_filtered.wav'
    write_pcm_wav(cleaned_wav, cleaned)
    pause = np.zeros(round(.35*FS), dtype=np.int16)
    write_pcm_wav(dest/'audio_AB_compare.wav', np.concatenate((raw, pause, cleaned)))
    plot_audio(raw, cleaned, dest/'audio_analysis.png')

    # Side-by-side comparison: ONE cleaned soundtrack (a video cannot play two
    # separate soundtracks simultaneously). WAV A/B supplies audible contrast.
    checkpoint(cancel_event)
    notify(progress,'media_export',0,2)
    replace_soundtrack(result.side_by_side, cleaned_wav,cancel_event=cancel_event)
    checkpoint(cancel_event)
    notify(progress,'media_export',1,2)
    final = dest / 'final_stabilised_filtered_audio.mp4'
    write_finished_video(result.side_by_side, final,cancel_event=cancel_event)
    checkpoint(cancel_event)
    notify(progress,'media_export',2,2)
    audio_measure = analyze(raw, cleaned)
    fir_measure = analyze(raw, fir_cleaned)
    audio_verified = port is not None and jobs > 0
    metrics['audio_filtering'] = {
        'status': 'PHYSICAL FPGA BIT-EXACT' if audio_verified else 'SOFTWARE REFERENCE ONLY',
        'hardware_verified': audio_verified, 'sample_rate_hz': FS,
        'channels': 1, 'samples': len(raw), 'duration_s': len(raw)/FS,
        'decoded_audio_samples': len(decoded_audio),
        'audio_end_silence_padding_samples': missing_samples,
        'audio_end_trimmed_samples': trimmed_samples,
        'filter': '17-tap 3.2 kHz low-pass at 16 kHz, mono',
        'job_count': jobs, 'analysis': audio_measure,
        'fir_only_analysis': fir_measure, 'cleanup_mode': audio_cleanup,
        'host_spectral_enhancement': host_enhancement,
        'final_audio_processing': ('FPGA FIR verified + HOST adaptive denoiser (hybrid)'
                                   if audio_verified and host_enhancement else
                                   'HOST FIR reference + HOST adaptive denoiser'
                                   if host_enhancement else
                                   'PHYSICAL FPGA FIR ONLY' if audio_verified else
                                   'SOFTWARE FIR REFERENCE ONLY'),
        'limitations': 'FIR is a 3.2 kHz low-pass; optional host spectral enhancement estimates noise from quieter frames. Neither guarantees speech clarity or full separation of overlapping sea/wind/engine noise.'
    }
    metrics['combined_output'] = final.name
    metrics['comparison_audio'] = 'Filtered audio is used on the side-by-side MP4; original vs filtered WAV available separately.'
    metrics['combined_hardware_verified'] = bool(metrics.get('hardware_verified') and audio_verified)
    metrics['final_media_fully_fpga_processed'] = False  # PC always performs warping / AAC, adaptive stage is HOST
    metrics['hybrid_host_audio_enhancement'] = bool(host_enhancement)
    metrics['end_to_end_wall_s'] = round(time.perf_counter()-started, 3)
    (dest/'metrics.json').write_text(json.dumps(metrics, indent=2)+'\n', encoding='utf-8')
    (dest/'combined_metrics.json').write_text(json.dumps({
        'source_file': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'processing': processing, 'mode': 'PHYSICAL FPGA' if port else 'SOFTWARE REFERENCE',
        'both_hardware_verified': metrics['combined_hardware_verified'],
        'final_media_fully_fpga_processed': False, 'host_audio_enhancement': bool(host_enhancement),
        'video_image_stability': metrics.get('image_stability',{}),
        'video_visual_outcome': metrics.get('visual_outcome'),
        'audio': metrics['audio_filtering'], 'output': final.name,
        'end_to_end_wall_s': metrics['end_to_end_wall_s'],
    }, indent=2)+'\n',encoding='utf-8')
    with (dest/'RUN_REPORT.md').open('a',encoding='utf-8') as fp:
        fp.write('\n## Unified video + audio DSP\n\n'
                 f"**Video FIR:** {metrics['mode']}\n\n"
                 f"**Audio FIR:** {metrics['audio_filtering']['status']}\n\n"
                 f"**Both physical paths verified:** {metrics['combined_hardware_verified']}\n\n"
                 f"**Audio cleanup:** {audio_cleanup}; HOST spectral stage: {bool(host_enhancement)}\n\n"
                 f"**High-band (5–7.5 kHz) change:** {audio_measure['high_band_5_7k5_attenuation_db']} dB\n\n"
                 f"**Combined MP4:** `{final.name}`\n\n"
                 'The FPGA is used only for the numerical FIR jobs; optional adaptive spectral enhancement runs on the PC. The soundtrack in the '
                 'side-by-side video is filtered; compare the two WAVs separately. '
                 'No perceptual audio-quality claim follows from band attenuation alone.\n')
    # Update GUI-visible elapsed time and report, preserving the existing video
    # metrics structure used in Assessment.
    result.elapsed_s = metrics['end_to_end_wall_s']
    return result


def main() -> None:
    p = argparse.ArgumentParser(description='Process one source MP4 through both motion and speech-band FIR paths')
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--out', type=Path, default=Path('videos/sim/unified_demo'))
    p.add_argument('--port', help='Physical COM port; MUST use v0.9+ dual-bank bitstream')
    p.add_argument('--profile', choices=['Normal','Strong'], default='Normal')
    p.add_argument('--processing', choices=PROCESSING_MODES, default='Video + Audio')
    p.add_argument('--audio-cleanup', choices=AUDIO_CLEANUP_MODES, default='Maritime adaptive')
    options = p.parse_args()
    result = run_unified_pipeline(options.video,None,options.out,options.port,
                                  profile=options.profile,processing=options.processing, audio_cleanup=options.audio_cleanup)
    print(json.dumps({'source':result.video.name,'comparison':str(result.side_by_side),
                      'final':result.metrics.get('combined_output'),
                      'hardware_verified':result.metrics.get('combined_hardware_verified',False),
                      'audio':result.metrics['audio_filtering']},indent=2))


if __name__ == '__main__':
    main()

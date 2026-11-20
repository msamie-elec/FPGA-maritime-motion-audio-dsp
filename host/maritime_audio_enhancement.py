"""Conservative offline maritime background-noise reduction (HOST / CPU ONLY).

Stage order: FPGA-verified (or software-reference) 17-tap audio FIR -> host STFT
noise-profile estimation -> soft Wiener spectral suppression with protective floor.

No neural speech separation, speech recognition, or claim to eliminate sound
in-band with speech.  Input and output are 16-kHz mono PCM16 of equal length.
"""
from __future__ import annotations

import numpy as np

FS = 16000
FFT = 512
HOP = 128
WINDOW = np.hanning(FFT).astype(np.float64)  # overlap-add normalization


def _stft(x: np.ndarray) -> np.ndarray:
    # Reflect at frame edges; support tiny clips as well as >30-second videos.
    pad = FFT // 2
    mode = 'reflect' if len(x) > 1 else 'edge'
    xp = np.pad(x, (pad, pad + HOP), mode=mode)
    frame_starts = np.arange(0, len(x) + HOP, HOP)
    indices = frame_starts[:, None] + np.arange(FFT)[None, :]
    frames = xp[indices] * WINDOW
    return np.fft.rfft(frames, axis=-1)


def _istft(spec: np.ndarray, samples: int) -> np.ndarray:
    # Account for the window overlap; a full test checks near-identity with
    # spectral gain=1. No intentional latency is added to exported audio.
    length = (len(spec) - 1) * HOP + FFT
    out = np.zeros(length, dtype=np.float64)
    window_sum = np.zeros(length, dtype=np.float64)
    frames = np.fft.irfft(spec, n=FFT, axis=-1)
    for i in range(len(spec)):
        a = i * HOP
        out[a:a + FFT] += frames[i] * WINDOW
        window_sum[a:a + FFT] += WINDOW ** 2
    out /= np.maximum(window_sum, 1e-8)
    return out[FFT // 2: FFT // 2 + samples]


def _db_ratio(after: float, before: float) -> float | None:
    if before <= 1e-12:
        return None
    return round(float(10 * np.log10(max(after, 1e-12) / before)), 2)


def suppress_maritime_noise(pcm: np.ndarray, strength: float = 1.0) -> tuple[np.ndarray, dict]:
    """Denoise through an estimated quiet-frame spectrum, **without** ground truth.

    Returns (PCM16, diagnostic metadata). This is a CPU post-processing stage;
    it never affects the numerical verification of the preceding FPGA FIR.
    """
    x16 = np.asarray(pcm, dtype=np.int16)
    if x16.ndim != 1:
        raise ValueError('Expected mono PCM16')
    if len(x16) < FFT:
        raise ValueError('Audio is too short for reliable 32-ms spectral frames')
    if not (0.25 <= strength <= 1.8):
        raise ValueError('Strength must be between 0.25 and 1.8')
    x = x16.astype(np.float64) / 32768.0
    if np.max(np.abs(x)) < 1e-6:
        return x16.copy(), dict(stage='HOST ADAPTIVE SPECTRAL', quiet_frames=0,
                                reduction_db=0.0, note='Silent audio left unchanged')
    stft = _stft(x)
    power = np.abs(stft) ** 2
    energy = np.mean(power, axis=1)
    # The bottom fifth of full-band energy windows is our noise proxy. It is
    # intentionally NOT reported as an objective true SNR estimate.
    cutoff = np.percentile(energy, 20)
    quiet = energy <= cutoff
    n_quiet = int(np.count_nonzero(quiet))
    noise = np.median(power[quiet], axis=0)
    noise = np.maximum(noise, np.max(power) * 1e-10 + 1e-14)
    contrast = float(np.median(energy) / max(cutoff, 1e-12))
    # Few quiet periods => avoid aggressive removal that can damage speech.
    alpha = (1.65 if contrast > 1.65 else (0.4 if contrast > 1.2 else 0.0)) * strength
    gain = 1.0 - alpha * noise[None, :] / np.maximum(power, 1e-14)
    gain = np.clip(gain, 0.18, 1.0)
    # Smooth gains in frequency to reduce isolated musical-noise bins.
    padded = np.pad(gain, ((0, 0), (2, 2)), mode='edge')
    gain = (padded[:, :-4] + 2*padded[:, 1:-3] + 3*padded[:, 2:-2] +
            2*padded[:, 3:-1] + padded[:, 4:]) / 9.0
    # Smooth in time as well to avoid audible gating/warbling during speech.
    for i in range(1, len(gain)):
        gain[i] = .60 * gain[i-1] + .40 * gain[i]
    # Additional marine rumble high-pass, with a gentle ramp over speech lows.
    hz = np.fft.rfftfreq(FFT, d=1.0/FS)
    rumble = np.clip((hz - 70.0) / (160.0 - 70.0), 0, 1)
    gain *= rumble[None, :]
    filtered = _istft(stft * gain, len(x16))
    y = np.clip(np.rint(filtered * 32768.0), -32768, 32767).astype(np.int16)
    # Simple objective diagnostics, explicitly not a speech-quality metric.
    original_rms = float(np.mean(x*x))
    filtered_rms = float(np.mean((y.astype(np.float64)/32768)**2))
    return y, {
        'stage': 'HOST ADAPTIVE SPECTRAL — NOT FPGA',
        'quiet_frames': n_quiet, 'total_frames': len(energy),
        'quiet_frame_contrast': round(contrast, 2),
        'strength': strength, 'frequency_floor_hz': 70,
        'rumble_transition_hz': 160,
        'signal_energy_change_db': _db_ratio(filtered_rms, original_rms),
        'note': 'Adaptive noise estimate is inferred from lower-energy frames, not isolated true noise. Voice and noise overlap; intelligibility improvement is not guaranteed.'
    }

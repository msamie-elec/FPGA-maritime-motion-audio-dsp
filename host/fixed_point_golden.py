"""Bit-exact reference for the maritime camera-motion FIR.

Sample format: signed 24-bit Q16.8 motion units.
Coefficient format: signed 16-bit Q1.15.
Product: signed 40 bits, accumulated in signed 48-bit.
Arithmetic right-shift by 15 (flooring negative values), then saturate to 24 bits.
Causal state: history[0] is the most recently accepted input sample.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

TAPS = 17
IN_BITS = 24
COEFF_BITS = 16
ACC_BITS = 48
SHIFT = 15
SAMPLE_MIN = -(1 << (IN_BITS - 1))
SAMPLE_MAX = (1 << (IN_BITS - 1)) - 1
COEFF_MIN = -(1 << (COEFF_BITS - 1))
COEFF_MAX = (1 << (COEFF_BITS - 1)) - 1


def load_coefficients(path: str | Path | None = None) -> tuple[int, ...]:
    if path is None:
        path = Path(__file__).resolve().parents[1] / 'hardware' / 'rtl' / 'fir_coefficients.txt'
    values = tuple(int(line.strip()) for line in Path(path).read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))
    if len(values) != TAPS:
        raise ValueError(f'Expected {TAPS} FIR coefficients, got {len(values)}')
    if any(not COEFF_MIN <= c <= COEFF_MAX for c in values):
        raise ValueError('FIR coefficient outside signed Q1.15 range')
    if values != values[::-1]:
        raise ValueError('FIR coefficients are not symmetric')
    if sum(values) != 1 << SHIFT:
        raise ValueError('FIR coefficients do not have integer unity DC gain')
    return values


def coefficient_sha256(path: str | Path | None = None) -> str:
    if path is None:
        path = Path(__file__).resolve().parents[1] / 'hardware' / 'rtl' / 'fir_coefficients.txt'
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saturate24(v: int) -> int:
    return max(SAMPLE_MIN, min(SAMPLE_MAX, v))


class FirReference:
    def __init__(self, coefficients: tuple[int, ...] | None = None):
        self.coefficients = coefficients if coefficients is not None else load_coefficients()
        if len(self.coefficients) != TAPS:
            raise ValueError('Incorrect number of FIR taps')
        self.history = [0] * TAPS

    def reset(self) -> None:
        self.history[:] = [0] * TAPS

    def step(self, x: int) -> int:
        if not SAMPLE_MIN <= x <= SAMPLE_MAX:
            raise ValueError('24-bit signed input sample out of range')
        self.history[1:] = self.history[:-1]
        self.history[0] = int(x)
        acc = sum(h*c for h, c in zip(self.history, self.coefficients))
        if not -(1 << 47) <= acc < (1 << 47):
            raise OverflowError('48-bit accumulator exceeded')
        return saturate24(acc >> SHIFT)

    def process(self, samples: list[int]) -> list[int]:
        return [self.step(x) for x in samples]


def to_hex24(x: int) -> str:
    if not SAMPLE_MIN <= x <= SAMPLE_MAX:
        raise ValueError('Cannot encode out of range 24-bit sample')
    return f'{x & 0xFFFFFF:06x}'


def centered_smooth(samples: list[int], coeffs: tuple[int, ...] | None = None) -> list[int]:
    """Centered 17-tap FIR with edge replication; uses causal RTL semantics.

    Pad 8 at each edge, run the causal filter, select y[i+16] for frame i.
    IMPORTANT: This is a geometry reference, not output from actual FPGA hardware.
    """
    if not samples:
        return []
    pad = TAPS//2
    ref = FirReference(coeffs)
    result = ref.process([samples[0]]*pad + samples + [samples[-1]]*pad)
    return result[TAPS-1:TAPS-1+len(samples)]

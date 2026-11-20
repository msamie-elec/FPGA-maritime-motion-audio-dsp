"""Physical Arty A7 verification of both independent FIR coefficient banks.

Requires: the NEW dual-bank bitstream on a real device, and a free USB-UART
COM port. Never substitutes a software model for an unavailable FPGA response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from design_audio_coefficients import design as audio_coefficients
from fixed_point_golden import FirReference, load_coefficients
from fpga_serial_client import run_batch


def main() -> None:
    ap = argparse.ArgumentParser(description='Verify real Arty A7 motion AND audio coefficient banks over USB-UART')
    ap.add_argument('--port', required=True, help='Physical UART, e.g. COM4')
    ap.add_argument('--json-out', type=Path, default=None, help='Optional physical evidence JSON')
    args = ap.parse_args()
    motion = load_coefficients()
    audio = audio_coefficients()
    if motion == audio:
        raise RuntimeError('Motion and audio coefficient banks are identical: invalid source configuration')

    impulse = [32768] + [0] * 47
    alternating = [((1 if n % 2 else -1) * (1000 + 37 * n)) for n in range(40)]
    cases = [
        ('motion_impulse', 0x11, impulse, motion),
        ('audio_impulse', 0x81, impulse, audio),
        ('audio_mixed_sign', 0x82, alternating, audio),
        ('motion_after_audio', 0x12, impulse, motion),
    ]
    observations = []
    started = time.perf_counter()
    for name, job_id, samples, coeffs in cases:
        expected = FirReference(coeffs).process(samples)
        actual = run_batch(args.port, samples, job_id=job_id)
        if actual != expected:
            failure = next((i for i, (received, reference) in enumerate(zip(actual, expected))
                            if received != reference), min(len(actual), len(expected)))
            got = actual[failure] if failure < len(actual) else '<missing>'
            want = expected[failure] if failure < len(expected) else '<missing>'
            raise AssertionError(f'{name} FAILED at sample {failure}: FPGA={got}, reference={want}; '
                                 'verify NEW dual-bank bitstream, serial connection, and RTL')
        print(f'PASS PHYSICAL FPGA {name}: job=0x{job_id:02X}, {len(samples)} bit-exact samples', flush=True)
        observations.append({'name': name, 'job_id': job_id, 'sample_count': len(samples),
                             'bit_exact': True})

    evidence = {
        'physical_fpga_verified': True, 'port': args.port,
        'motion_coefficient_sha256': hashlib.sha256(
            Path(__file__).resolve().parents[1].joinpath('rtl/fir_coefficients.txt').read_bytes()
        ).hexdigest(),
        'audio_coefficient_sha256': hashlib.sha256(
            Path(__file__).resolve().parents[1].joinpath('rtl/audio_coefficients.txt').read_bytes()
        ).hexdigest(),
        'cases': observations, 'elapsed_s': round(time.perf_counter() - started, 3),
        'note': 'A physical UART response was checked for every sample. This test does not measure video/image or subjective audio quality.',
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('DUAL_BANK_PHYSICAL_FPGA_PASS: 4 independent UART/FIR jobs, motion/audio/motion switching verified')


if __name__ == '__main__':
    main()

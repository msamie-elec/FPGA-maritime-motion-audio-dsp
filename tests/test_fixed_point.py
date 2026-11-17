"""Reference-model and reproducibility tests. NOT a substitute for RTL simulation."""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))

from fixed_point_golden import (FirReference, TAPS, SAMPLE_MAX, SAMPLE_MIN,
    centered_smooth, coefficient_sha256, load_coefficients, saturate24, to_hex24)
from generate_vectors import RANDOM_SEED, cases
from design_coefficients import design


def test_coefficients_frozen_symmetric_dc_gain():
    c=load_coefficients()
    assert len(c)==17 and c==tuple(reversed(c))
    assert sum(c)==32768 and c==tuple(design())
    assert coefficient_sha256() == 'dcd20f90279e4d32f88aface3dfc0be25e94569122e1cba2e365970989cf1e7b'


def test_coeff_rom_matches_text():
    inc=(ROOT/'rtl'/'fir_coefficients.svh').read_text()
    coeff=load_coefficients()
    for i,c in enumerate(coeff):
        val=f"16'sd{c}" if c>=0 else f"-16'sd{-c}"
        assert f"5'd{i}: coeff_at = {val};" in inc


def direct_convolution(samples):
    c=load_coefficients()
    result=[]
    for n in range(len(samples)):
        # Independent reference expression: direct causal convolution.
        acc=sum(c[k]*samples[n-k] for k in range(TAPS) if n-k>=0)
        result.append(saturate24(math.floor(acc/(1<<15))))
    return result


def test_exact_against_independent_direct_convolution():
    for name,x in cases().items():
        f=FirReference()
        assert f.process(x) == direct_convolution(x), name


def test_dc_unity_after_warmup_and_sign():
    for val in [0,1,-1,256*42,-256*77,SAMPLE_MAX,SAMPLE_MIN]:
        f=FirReference()
        out=f.process([val]*72)
        assert out[-1]==val


def test_reset_clears_history():
    f=FirReference()
    f.process([SAMPLE_MAX]*25)
    f.reset()
    assert f.process([0]*40)==[0]*40


def test_saturation_and_negative_arithmetic_shift():
    assert saturate24(1<<40)==SAMPLE_MAX
    assert saturate24(-(1<<40))==SAMPLE_MIN
    c=load_coefficients()
    f=FirReference()
    assert f.step(1)==math.floor(c[0]/(1<<15))
    assert f.step(-1)==math.floor((-c[0] + c[1])/(1<<15))


def test_out_of_range_input_rejected():
    f=FirReference()
    for val in [SAMPLE_MAX+1,SAMPLE_MIN-1]:
        try:
            f.step(val)
            raise AssertionError('out-of-range input accepted')
        except ValueError:
            pass


def test_centered_alignment_and_constant_boundary():
    const=[123456]*111
    assert centered_smooth(const)==const
    length=80
    impulse=[0]*length
    impulse[40]=32768
    out=centered_smooth(impulse)
    assert len(out)==len(impulse)
    assert max(range(length),key=lambda i:out[i])==40
    assert out[32:49]==out[32:49][::-1]


def test_vectors_identical_to_generator_outputs():
    manifest=json.loads((ROOT/'tests'/'vectors'/'vector_manifest.json').read_text())
    assert manifest['seed']==RANDOM_SEED
    assert manifest['coefficient_sha256']==coefficient_sha256()
    assert set(manifest['cases'])==set(cases())
    for name,x in cases().items():
        expected=FirReference().process(x)
        i_file=ROOT/'tests'/'vectors'/f'{name}_input.mem'
        o_file=ROOT/'tests'/'vectors'/f'{name}_expected.mem'
        assert i_file.read_text().splitlines()==[to_hex24(v) for v in x]
        assert o_file.read_text().splitlines()==[to_hex24(v) for v in expected]
        assert hashlib.sha256(i_file.read_bytes()).hexdigest()==manifest['cases'][name]['input_sha256']
        assert hashlib.sha256(o_file.read_bytes()).hexdigest()==manifest['cases'][name]['expected_sha256']


def test_motion_frequency_response_numerical():
    c=load_coefficients()
    def gain(f):
        z=sum(coef*complex(math.cos(-2*math.pi*f*k/30),math.sin(-2*math.pi*f*k/30)) for k,coef in enumerate(c)) / 32768
        return abs(z)
    assert abs(gain(0)-1)<1e-10
    assert gain(0.25)>0.98
    assert gain(6)<0.01
    assert gain(10)<0.01


def test_input_vector_lengths_fit_host_batch_scope():
    assert all(len(v) <= 512 for v in cases().values())

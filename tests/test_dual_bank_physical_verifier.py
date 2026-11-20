"""Host-only test of physical verification control flow. This is NOT hardware evidence."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))

from design_audio_coefficients import design as audio_coeffs
from fixed_point_golden import FirReference, load_coefficients
import verify_dual_bank_fpga
import fpga_serial_client


def test_dual_bank_verifier_tests_both_banks_and_restore(monkeypatch, tmp_path):
    jobs = []

    def stub_uart(port, samples, job_id):
        assert port == 'MOCK_UART_NOT_PHYSICAL'
        jobs.append(job_id)
        coeffs = audio_coeffs() if job_id & 0x80 else load_coefficients()
        return FirReference(coeffs).process(samples)

    monkeypatch.setattr(verify_dual_bank_fpga, 'run_batch', stub_uart)
    path = tmp_path / 'physical_report.json'
    monkeypatch.setattr(sys, 'argv', ['verify_dual_bank_fpga.py', '--port', 'MOCK_UART_NOT_PHYSICAL', '--json-out', str(path)])
    verify_dual_bank_fpga.main()
    assert jobs == [0x11, 0x81, 0x82, 0x12]
    result = json.loads(path.read_text())
    assert len(result['cases']) == 4
    assert result['physical_fpga_verified'] is True  # mock verified control flow only


def test_dual_bank_verifier_rejects_mismatched_fpga(monkeypatch, tmp_path):
    monkeypatch.setattr(verify_dual_bank_fpga, 'run_batch',
                        lambda port, samples, job_id: [0] * len(samples))
    monkeypatch.setattr(sys, 'argv', ['verify_dual_bank_fpga.py', '--port', 'MOCK_UART_NOT_PHYSICAL'])
    with pytest.raises(AssertionError, match='motion_impulse FAILED'):
        verify_dual_bank_fpga.main()

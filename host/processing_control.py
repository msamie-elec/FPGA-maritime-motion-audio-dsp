"""Cooperative cancellation and truthful progress for offline UART/host jobs.

Cancellation is checked BETWEEN complete UART transactions; no mid-packet
abort or FPGA reset is attempted. No cancellation is called a hardware PASS.
"""
from __future__ import annotations
from typing import Callable

Progress = Callable[[str, int, int], None]

class ProcessingCancelled(Exception):
    """Operator requested cancellation of an unfinished processing run."""

def checkpoint(cancel_event=None):
    if cancel_event is not None and cancel_event.is_set():
        raise ProcessingCancelled('Processing cancelled at a safe checkpoint')

def progress(callback: Progress | None, stage: str, current: int = 0, total: int = 1):
    if callback is not None:
        callback(stage, current, max(1, total))


def run_process(args, *, cancel_event=None, timeout=240, text=False):
    """Capture a subprocess while allowing cancellation between polling intervals.

    No cancellation request makes this equivalent to subprocess.run. When
    cancelled, terminate/kill only the *host subprocess*, never the FPGA.
    """
    import subprocess
    import time
    if cancel_event is None:
        return subprocess.run(args, capture_output=True, timeout=timeout, text=text)
    checkpoint(cancel_event)
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=text) as proc:
        start=time.monotonic()
        try:
            while True:
                checkpoint(cancel_event)
                remaining=timeout-(time.monotonic()-start)
                if remaining<=0:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    stdout,stderr=proc.communicate(timeout=min(.25,remaining))
                    checkpoint(cancel_event)
                    return subprocess.CompletedProcess(args,proc.returncode,stdout,stderr)
                except subprocess.TimeoutExpired:
                    continue
        except (ProcessingCancelled,subprocess.TimeoutExpired):
            proc.terminate()
            try:proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill();proc.communicate()
            raise

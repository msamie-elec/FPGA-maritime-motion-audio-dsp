"""Physical Arty A7 FIR client. NO fake FPGA fallback in hardware mode."""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

from serial_protocol import SYNC, encode_request, decode_response, MAX_SAMPLES


def run_batch(port: str, samples: list[int], job_id: int = 1, baud: int = 115200) -> list[int]:
    try:
        import serial
    except ImportError as e:
        raise RuntimeError('Install pyserial: python -m pip install -r host/requirements.txt') from e
    request = encode_request(samples, job_id)
    timeout = max(3., (len(request) * 10 / baud) * 6 + 2)
    with serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=timeout) as ser:
        # Allow the board reset/USB adapter to settle; do not reset between axis jobs.
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        h = ser.read(8)
        if len(h) != 8:
            raise TimeoutError(f'incomplete response header {len(h)}/8 bytes')
        if h[:2] != SYNC:
            raise ValueError(f'invalid FPGA response prefix: {h.hex()}')
        n = int.from_bytes(h[6:8], 'little')
        if n > MAX_SAMPLES:
            raise ValueError('FPGA returned oversize packet')
        tail = ser.read(3*n+2)
        if len(tail) != 3*n+2:
            raise TimeoutError(f'incomplete FPGA response payload: {len(tail)}/{3*n+2}')
        return decode_response(h+tail, job_id, len(samples))


def run_two_axes(port: str, x: list[int], y: list[int]) -> tuple[list[int], list[int]]:
    # Reopen the same USB COM port after the first response. Board remains powered.
    if len(x) != len(y) or not 1 <= len(x) <= MAX_SAMPLES:
        raise ValueError('axes must have equal length 1..512')
    return run_batch(port, x, 1), run_batch(port, y, 2)


def main() -> None:
    parser=argparse.ArgumentParser(description='Send signed Q16.8 motion samples to the REAL Arty A7 FIR accelerator')
    parser.add_argument('--port',required=True,help='Windows COM port, e.g. COM6')
    parser.add_argument('--input',required=True,help='JSON list of integer Q16.8 samples')
    parser.add_argument('--output',required=True,help='File to store verified FPGA response samples')
    parser.add_argument('--job-id',type=int,default=1)
    args=parser.parse_args()
    samples=json.loads(Path(args.input).read_text())
    before=time.perf_counter()
    result=run_batch(args.port,samples,args.job_id)
    elapsed=time.perf_counter()-before
    Path(args.output).write_text(json.dumps({'mode':'physical_fpga','port':args.port,'samples':result,'input_count':len(samples),'round_trip_s':elapsed},indent=2)+'\n')
    print(f'FPGA response CRC/count verified: {len(result)} samples, elapsed {elapsed:.3f} s')

if __name__=='__main__':
    main()

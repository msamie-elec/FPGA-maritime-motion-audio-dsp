"""Require a physical Artix-7 UART response; abort on any numerical mismatch."""
from __future__ import annotations
import argparse
from fpga_serial_client import run_batch
from fixed_point_golden import FirReference


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',required=True,help='Arty A7 UART COM port, e.g. COM6')
    args=ap.parse_args()
    cases={
      'impulse':[32768]+[0]*31,
      'negative_dc':[-3840]*64,
      'random_like':[(-1 if i%2 else 1)*(23000+(i*8899)%33000) for i in range(80)],
    }
    for idx,(name,samples) in enumerate(cases.items(),1):
        expected=FirReference().process(samples)
        received=run_batch(args.port,samples,job_id=idx)
        if received!=expected:
            ix=next(i for i,(a,b) in enumerate(zip(received,expected)) if a!=b)
            raise AssertionError(f'{name}: FPGA mismatch at index {ix}, got {received[ix]}, expected {expected[ix]}')
        print(f'PASS PHYSICAL FPGA {name}: {len(samples)} bit-exact samples')
    print('MARITIME_PHYSICAL_UART_FIR_SMOKE_PASS - 3 hardware jobs')

if __name__=='__main__': main()

"""Deterministic FIR vectors for self-checking SystemVerilog and Python tests."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from pathlib import Path

from fixed_point_golden import FirReference, SAMPLE_MAX, SAMPLE_MIN, centered_smooth, load_coefficients, to_hex24

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'tests'/'vectors'
RANDOM_SEED = 20261117


def cases() -> dict[str, list[int]]:
    rng = random.Random(RANDOM_SEED)
    # RAW signed 24-bit integer motion coordinates, where 256 units = 1 px.
    impulse = [256*320] + [0]*95
    dc = [256*120]*96
    negative_dc = [-256*140]*96
    ramp = [int(round((i-63.5)*256*2)) for i in range(128)]
    random_values = [rng.randint(SAMPLE_MIN, SAMPLE_MAX) for _ in range(512)]
    extremes = ([SAMPLE_MAX,SAMPLE_MIN,0,1,-1,256,-256]*19)[:128]
    zeros = [0]*64
    # Synthetic slow camera pan + waves, pitches, vibrations, deterministic.
    shake = [int(round(256*(65 + 0.42*n + 8.5*math.sin(2*math.pi*.3*n/30)
               + 5.5*math.sin(2*math.pi*6*n/30)
               + 2.7*math.sin(2*math.pi*9*n/30)))) for n in range(256)]
    return dict(impulse=impulse,dc=dc,negative_dc=negative_dc,ramp=ramp,
                random=random_values,extremes=extremes,zeros=zeros,shake=shake)


def main() -> None:
    DEST.mkdir(parents=True,exist_ok=True)
    metadata = {'seed':RANDOM_SEED,'format':'signed24_Q16.8','coefficient_sha256':None,'cases':{},'reference_only':True}
    coeffs=load_coefficients()
    ref = FirReference(coeffs)
    # Freeze LF at the byte level to keep vector SHA-256 stable on Windows/Linux.
    for name, samples in cases().items():
        ref.reset()
        expected = ref.process(samples)
        in_file=DEST/f'{name}_input.mem'
        out_file=DEST/f'{name}_expected.mem'
        in_file.write_bytes(''.join(to_hex24(x)+'\n' for x in samples).encode('utf-8'))
        out_file.write_bytes(''.join(to_hex24(y)+'\n' for y in expected).encode('utf-8'))
        metadata['cases'][name]={'samples':len(samples),'reference_min':min(expected),'reference_max':max(expected),
            'input_sha256':hashlib.sha256(in_file.read_bytes()).hexdigest(),
            'expected_sha256':hashlib.sha256(out_file.read_bytes()).hexdigest()}
    coeff_path=ROOT/'rtl'/'fir_coefficients.txt'
    metadata['coefficient_sha256']=hashlib.sha256(coeff_path.read_bytes()).hexdigest()
    (DEST/'vector_manifest.json').write_bytes((json.dumps(metadata,indent=2,sort_keys=True)+'\n').encode('utf-8'))
    # Test the planned centered-video alignment convention with a deterministic trajectory.
    padded_test = cases()['shake']
    aligned = centered_smooth(padded_test)
    with (DEST/'shake_centered_trajectory.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['frame_index','raw_q16_8','software_centered_filtered_q16_8','raw_pixels','software_filtered_pixels'])
        for i,(a,b) in enumerate(zip(padded_test,aligned)):
            writer.writerow([i,a,b,a/256,b/256])
    print('Generated',sum(len(v) for v in cases().values()),'reference-only sample vectors across',len(cases()),'cases')


if __name__=='__main__':
    main()

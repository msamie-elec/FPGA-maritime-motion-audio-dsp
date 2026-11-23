#!/usr/bin/env python3
"""Real USB-UART dual-bank reliability campaign. No software fallback in physical mode.
Cold: 5 manual power/reprogram cycles and first+warm sets.
Soak: sustained workload at natural operating temperature; not qualification temperature testing.
"""
from __future__ import annotations
import argparse, csv, json, os, random, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'host'))
from design_audio_coefficients import design as audio_coefficients
from fixed_point_golden import FirReference, load_coefficients
from fpga_serial_client import run_batch

FIELDS=['timestamp_utc','phase','cycle','repeat','case','job_id','sample_count','passed','elapsed_s','first_mismatch','exception','operator_note']

def make_cases(index, random_seed):
    rng=random.Random(random_seed+index)
    # Include boundary full-sized audio packet periodically, without 512 jobs every cycle.
    n=512 if index%5==0 else 64
    return [
      ('motion_impulse',0x11,[32768]+[0]*63,False),
      ('audio_random',0x81,[rng.randint(-2_000_000,2_000_000) for _ in range(n)],True),
      ('audio_mixed_sign',0x82,[(-1 if i%2 else 1)*(30000+(i*117)%200000) for i in range(64)],True),
      ('motion_after_audio',0x12,[rng.randint(-1_000_000,1_000_000) for _ in range(64)],False),
    ]

def run_set(port, phase, cycle, repeat, seed, csv_writer, csv_fd, operator_note):
    cases=make_cases(cycle+repeat,seed)
    obs=[]
    for name, job_id, samples, audio in cases:
        stamp=datetime.now(timezone.utc).isoformat()
        start=time.perf_counter()
        mismatch='';err='';passed=False
        try:
            coeffs=audio_coefficients() if audio else load_coefficients()
            expected=FirReference(coeffs).process(samples)
            actual=run_batch(port,samples,job_id=job_id)
            mismatch=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),None)
            if len(actual)!=len(expected):mismatch=min(len(actual),len(expected))
            passed=mismatch is None
            if not passed:err=f'bit-exact mismatch at sample {mismatch}'
        except Exception as exc:
            err=f'{type(exc).__name__}: {exc}'
        row={'timestamp_utc':stamp,'phase':phase,'cycle':cycle,'repeat':repeat,'case':name,
             'job_id':f'0x{job_id:02x}','sample_count':len(samples),'passed':passed,
             'elapsed_s':round(time.perf_counter()-start,6),'first_mismatch':mismatch,
             'exception':err,'operator_note':operator_note}
        csv_writer.writerow(row);csv_fd.flush();os.fsync(csv_fd.fileno());obs.append(row)
        print(f"{phase} cycle={cycle} repeat={repeat} {name} {'PASS' if passed else 'FAIL'} elapsed={row['elapsed_s']:.3f}s {err}",flush=True)
    return obs

def summary(rows,port,mode,arguments,source):
    all_count=len(rows);fail=[r for r in rows if not r['passed']]
    elapsed=[float(r['elapsed_s']) for r in rows if isinstance(r.get('elapsed_s'), (int,float)) and r['elapsed_s']>0]
    total_samples=sum(int(r['sample_count']) for r in rows if isinstance(r.get('sample_count'),int))
    return {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'physical_port':port,
        'mode':mode,'total_jobs':all_count,'passing_jobs':all_count-len(fail),
        'failed_jobs':len(fail),'all_passed':all_count>0 and len(fail)==0,
        'tested_samples_including_failed_jobs':total_samples,
        'uart_roundtrip_median_ms':round(statistics.median(elapsed)*1000,2) if elapsed else None,
        'uart_roundtrip_p95_ms':round(sorted(elapsed)[min(len(elapsed)-1,max(0,int(len(elapsed)*.95)-1))]*1000,2) if elapsed else None,
        'effective_host_uart_samples_per_s':round(total_samples/sum(elapsed),2) if elapsed else None,
        'first_run_jobs':sum(1 for r in rows if r['repeat']==0),
        'first_run_failures':sum(1 for r in rows if r['repeat']==0 and not r['passed']),
        'configuration':arguments,'operator_manifest':source,
        'limitations':['The UART throughput includes failed job inputs; host serial port open/close and protocol overhead are included. This is NOT FPGA-native sample throughput.',
        'This logs host UART round-trips and bit exactness; not FPGA cycle-level latency.',
        'Cold/power/reset actions are manually reported, not electrically sensed.',
        'Hot/soak means ordinary workload warming, not qualified external high-temperature operation.',
        'Die temperature requires separate Hardware Manager XADC snapshots.']}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',required=True)
    ap.add_argument('--mode',choices=['cold','reset','soak'],required=True)
    ap.add_argument('--cycles',type=int,default=5)
    ap.add_argument('--warm-runs',type=int,default=1)
    ap.add_argument('--minutes',type=float,default=15.0)
    ap.add_argument('--max-sets',type=int,default=5000)
    ap.add_argument('--settle-s',type=float,default=5.0)
    ap.add_argument('--seed',type=int,default=11020)
    ap.add_argument('--bitstream-sha256',default='UNCONFIRMED_ON_DEVICE')
    ap.add_argument('--output-dir',type=Path)
    args=ap.parse_args(argv)
    if args.cycles<1 or args.warm_runs<0 or args.minutes<=0 or args.max_sets<1 or args.settle_s<0:ap.error('Positive cycles/minutes/max-sets required')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=args.output_dir or ROOT/'evidence'/'final_validation'/f'{args.mode}_{stamp}'
    out.mkdir(parents=True,exist_ok=False)
    meta={'date':datetime.now(timezone.utc).isoformat(),'mode':args.mode,'port':args.port,
          'bitstream_sha256_operator_claim':args.bitstream_sha256,
          'note':'No automatic verification that device actually contains specified .bit, use Hardware Manager proof.'}
    (out/'operator_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    collected=[]
    with (out/'results.csv').open('w',newline='',encoding='utf-8') as fd:
        writer=csv.DictWriter(fd,fieldnames=FIELDS);writer.writeheader();fd.flush()
        def save():
            s=summary(collected,args.port,args.mode,vars(args) | {'output_dir':str(out)},meta)
            (out/'summary.json').write_text(json.dumps(s,indent=2,default=str)+'\n',encoding='utf-8')
        if args.mode in ('cold','reset'):
            for k in range(1,args.cycles+1):
                action=('Physically POWER-CYCLE, then REPROGRAM same .bit via Vivado Hardware Manager' if args.mode=='cold' else 'Press and RELEASE BTN0 (no power-cycle)')
                print(f'\nCycle {k}/{args.cycles}: {action}. Ensure COM port reconnects if needed.\nRecord screenshots/bit hash/temperature separately.',flush=True)
                answer=input('After action, enter READY (or SKIP to record an unperformed cycle): ').strip().upper()
                if answer!='READY':
                    row=dict.fromkeys(FIELDS,'');row.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),phase=args.mode,cycle=k,repeat=-1,case='operator_action_not_confirmed',passed=False,exception='Operator did not confirm action',operator_note=answer)
                    writer.writerow(row);fd.flush();collected.append(row);save();continue
                print(f'Settling {args.settle_s} seconds after confirmed operator action; this is not a measured start-up latency.',flush=True)
                time.sleep(args.settle_s)
                for j in range(args.warm_runs+1):
                    phase='first_after_'+args.mode if j==0 else 'warm_after_'+args.mode
                    collected.extend(run_set(args.port,phase,k,j,args.seed,writer,fd,action))
                    save()
        else:
            print('Warm-run SOAK mode: board stays powered; no external heating/cooling. Capture XADC before/during/after separately.',flush=True)
            start=time.monotonic();n=0
            while time.monotonic()-start < args.minutes*60 and n < args.max_sets:
                collected.extend(run_set(args.port,'soak',n+1,0,args.seed,writer,fd,'continuous powered operation'))
                n+=1;save()
        save()
    print('EVIDENCE_DIR',out)
    s=json.loads((out/'summary.json').read_text());print('TOTAL',s['total_jobs'],'PASS',s['passing_jobs'],'FAIL',s['failed_jobs'])
    if not s['all_passed']:raise SystemExit(1)
    print('MARITIME_PHYSICAL_RELIABILITY_PASS (bit-exact jobs only; report environmental/temperature evidence separately)')
if __name__=='__main__':main()

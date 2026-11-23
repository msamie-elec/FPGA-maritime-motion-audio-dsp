"""Evidence-driven GUI/release summary. No tools run automatically; never re-label archived evidence.

This module has no GUI dependency so its provenance and status logic is unit-tested.
"""
from __future__ import annotations
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence'/'reference_2026-11-21_revc'
LIVE=ROOT/'evidence'/'final_validation'

def _json(path):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError): return None

def read_xadc(root=ROOT):
    """Read real XADC snapshots; prefer local logs over archived operator evidence.

    An archived result is a historical measurement, not a fresh local sensor poll.
    """
    root=Path(root)
    live=root/'evidence'/'final_validation'/'xadc_snapshots.csv'
    archive=root/'evidence'/'xadc_2026-11-23'/'xadc_snapshots.csv'
    path=live if live.is_file() else archive
    result={'status':'NOT_MEASURED','source':None,'latest_c':None,'snapshots':[],
            'source_type':None,'count':0,'min_c':None,'max_c':None,
            'by_phase':{},'latest_phase':None}
    if not path.is_file():
        return result
    try:
        with path.open('r',encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                if row.get('source')!='Vivado_Hardware_Manager_XADC':
                    continue
                try:
                    c=float(row['die_temperature_c'])
                except (KeyError,TypeError,ValueError):
                    continue
                if not (-50.0<=c<=150.0):
                    continue
                result['snapshots'].append({'timestamp_local':row.get('timestamp_local',''),
                    'phase':row.get('phase','unspecified'),'die_temperature_c':c,
                    'source':row['source']})
    except (OSError,UnicodeError,csv.Error):
        return result
    if result['snapshots']:
        temps=[s['die_temperature_c'] for s in result['snapshots']]
        for phase in sorted(set(s['phase'] for s in result['snapshots'])):
            vals=[s['die_temperature_c'] for s in result['snapshots'] if s['phase']==phase]
            result['by_phase'][phase]={'n':len(vals),'mean_c':round(sum(vals)/len(vals),3),
                                       'min_c':min(vals),'max_c':max(vals)}
        result.update(status='MEASURED',source=str(path.relative_to(root)),
                      source_type='LOCAL_OPERATOR_CSV' if path==live else 'ARCHIVED_OPERATOR_CSV',
                      count=len(temps),min_c=min(temps),max_c=max(temps),
                      latest_c=temps[-1],latest_phase=result['snapshots'][-1]['phase'])
    return result

def _last_live(glob):
    paths=sorted(LIVE.glob(glob)) if LIVE.exists() else []
    return paths[-1] if paths else None

def collect(root=ROOT, live_metrics=None):
    root=Path(root)
    owner=root/'evidence'/'owner_2026-11-23_revd'
    base=(owner if (owner/'report_summary.json').is_file() else
          root/'evidence'/'reference_2026-11-21_revc' if
          (root/'evidence'/'reference_2026-11-21_revc'/'report_summary.json').is_file() else
          root/'evidence'/'reference_2026-11-20')
    live=root/'evidence'/'final_validation'
    builds=sorted(p for p in live.glob('build_*/report_summary.json') if p.is_file()) if live.exists() else []
    build=builds[-1] if builds else base/'report_summary.json'
    rpt=_json(build)
    timing=(rpt or {}).get('timing',{})
    resources=(rpt or {}).get('resource_counts',{})
    obs=_json(owner/'owner_console_observations.json') or {}
    observations=obs.get('test_runs',[])
    physical={}
    history=[]
    for run in observations:
        if run.get('mode') not in ('cold','reset','soak'): continue
        history.append({**run,'source':'evidence/owner_2026-11-23_revd/owner_console_observations.json'})
    for mode in ('cold','reset','soak'):
        candidates=sorted(live.glob(f'{mode}_*/summary.json')) if live.exists() else []
        for path in candidates:
            dat=_json(path)
            if dat:
                history.append({'mode':mode,'source':str(path.relative_to(root)),
                    'source_type':'original_machine_readable_json','run_directory':path.parent.name,
                    'total_jobs':dat.get('total_jobs'), 'passed_jobs':dat.get('passing_jobs'),
                    'failed_jobs':dat.get('failed_jobs'),'all_passed':dat.get('all_passed')})
        path=candidates[-1] if candidates else root/'evidence'/'reference_2026-11-20'/mode/'summary.json'
        dat=_json(path)
        if not candidates:
            # If the most recent screenshot exists, do not let an older 20-Nov log supersede it.
            # A source-only GitHub checkout has no older reference logs at all;
            # still present the dated screenshot as OBSERVED evidence, not a missing trial.
            screenshot_runs=[x for x in observations if x.get('mode')==mode]
            if screenshot_runs:
                chosen=screenshot_runs[-1]
                physical[mode]={'source':'evidence/owner_2026-11-23_revd/owner_console_observations.json',
                    'total_jobs':chosen.get('total_jobs'),'passing_jobs':chosen.get('passed_jobs'),
                    'failed_jobs':chosen.get('failed_jobs'),'samples':chosen.get('audio_samples'),
                    'all_passed':chosen.get('failed_jobs')==0,'port':'COM4',
                    'timestamp':chosen.get('date'),
                    'bitstream_identity':'UNCONFIRMED_ON_DEVICE',
                    'evidence_type':chosen.get('source_type'),
                    'raw_success_logs_present':False if chosen.get('source_type')=='user_console_screenshot' else True}
                continue
        if dat:
            physical[mode]={'source':str(path.relative_to(root)),
                'total_jobs':dat.get('total_jobs'),
                'passing_jobs':dat.get('passing_jobs'),
                'failed_jobs':dat.get('failed_jobs'),
                'samples':dat.get('tested_samples_including_failed_jobs'),
                'all_passed':dat.get('all_passed'),
                'port':dat.get('physical_port'),
                'timestamp':dat.get('timestamp_utc'),
                'bitstream_identity':dat.get('configuration',{}).get('bitstream_sha256','NOT VERIFIED'),
                'evidence_type':'original_machine_readable_json',
                'raw_success_logs_present':True}
    assessment=_json(root/'verification'/'model'/'generated'/'filter_assessment.json')
    quality=_json(root/'evidence'/'quality_2026-11-23_reference'/'quality_assessment.json')
    source_type=('LOCAL RUN — REPORT' if builds else
                 'OWNER UPLOADED — ARCHIVED RevD REPORTS' if base==owner else
                 'ARCHIVED REFERENCE REPORT')
    return {
        'project':'Maritime video-motion + audio FIR (hybrid PC / Arty A7)',
        'board':'Digilent Arty A7-35T',
        'scope':'Buffered UART FIR on FPGA; motion estimation, video warp, adaptive spectral audio cleanup on host',
        'report_provenance':str(build.relative_to(root)) if rpt else None,
        'report_source_type':source_type,
        'historical_baseline':not bool(builds),
        'clock_mhz':100,
        'timing':timing,
        'internal_timing_met':(rpt or {}).get('internal_timing_met'),
        'resources':resources,
        'estimated_power_w':(rpt or {}).get('estimated_power_w'),
        'xadc':read_xadc(root),
        'power_assumption':'Post-route vectorless estimate; no measured board power or workload SAIF',
        'unconstrained_external_io':(rpt or {}).get('unconstrained_io_mentioned'),
        'drc_rules':(rpt or {}).get('drc_rules',[]),
        'physical_campaign':physical,
        'physical_history':history,
        'filter_reference_assessment':assessment,
        'media_quality_reference':quality,
        'current_gui_run':live_metrics,
        'limitations':[
            'External UART/button/LED timing exceptions are not full I/O timing qualification; DSP pipeline advisories remain.',
            'RevD routed report source is owner-uploaded on 23 Nov 2026, not an implementation performed by this package.',
            'User-screen captured successful soak is not the original results CSV; import local raw files for evidence completeness.',
            'Earlier soak 141/4664 jobs failed due to Windows COM4 access denied; retain this as a distinct failed trial.',
            'Physical test log does not independently prove bitstream identity on the device.',
            ('Cold and reset actions were operator-controlled; soak is not temperature-chamber qualification; '
             + ('XADC die-temperature snapshots are separate, operator-labelled observations, not a continuously logged soak.'
                if read_xadc(root)['status']=='MEASURED' else 'XADC temperature not measured.')),
            'Host-side adaptive audio cleanup and image stabilisation are not FPGA logic.',
            'Bit-exact FIR tests do not independently establish visual shake reduction or speech intelligibility.',
        ],
    }

def _fmt(v, suffix=''):
    return 'NOT AVAILABLE' if v is None else str(v)+suffix

def to_markdown(s):
    t=s.get('timing',{});r=s.get('resources',{})
    lines=['# Maritime FPGA — Engineering Summary Report','',
        '> Archived evidence is not a rerun. Each result below names its source.','',
        f"**Platform:** {s['board']} | **Design clock:** {s['clock_mhz']} MHz",'',
        f"**Hardware boundary:** {s['scope']}",'',
        f"**Report source:** `{s['report_provenance'] or 'NOT AVAILABLE'}`",
        f"**Source classification:** {s['report_source_type']}",'',
        '## Routed implementation','','| Metric | Value |','|---|---:|',
        f"| WNS setup | {_fmt(t.get('setup_wns_ns'),' ns')} |",
        f"| TNS setup | {_fmt(t.get('setup_tns_ns'),' ns')} |",
        f"| WHS hold | {_fmt(t.get('hold_whs_ns'),' ns')} |",
        f"| THS hold | {_fmt(t.get('hold_ths_ns'),' ns')} |",
        f"| Internal timing met under existing constraints | {_fmt(s['internal_timing_met'])} |",
        f"| LUTs | {_fmt(r.get('luts'))} |",
        f"| Registers | {_fmt(r.get('registers'))} |",
        f"| DSP48E1 | {_fmt(r.get('dsp48e1'))} |",
        f"| RAMB18 | {_fmt(r.get('bram18'))} |",
        f"| Vectorless FPGA power | {_fmt(s['estimated_power_w'],' W')} |",'',
        f"**Power qualifier:** {s['power_assumption']}",
        f"**External I/O missing constraints flagged:** {_fmt(s['unconstrained_external_io'])}",'',
        '## Die temperature — physical XADC (not estimated power)', '']
    xadc=s.get('xadc',{})
    if xadc.get('status')=='MEASURED':
        lines.extend(['**Status:** MEASURED — Vivado Hardware Manager XADC, die only',
            f"**Data source:** `{xadc.get('source')}` ({xadc.get('source_type')})",
            f"**Snapshots:** {xadc.get('count')} | **Range:** {xadc.get('min_c'):.1f}–{xadc.get('max_c'):.1f}°C | Latest: {xadc.get('latest_c'):.1f}°C ({xadc.get('latest_phase')})",'',
            '| Operator phase | Samples | Mean die °C | Range °C |',
            '|---|---:|---:|---|'])
        for phase,stats in xadc.get('by_phase',{}).items():
            lines.append(f"| {phase} | {stats['n']} | {stats['mean_c']:.3f} | {stats['min_c']:.1f}–{stats['max_c']:.1f} |")
        lines+=['','Earlier `soak_end` labels were not backed by a confirmed soak. No actual during-workload trace or maximum temperature is claimed.','',
                '| Local timestamp | Phase (operator label) | Die temp (°C) |','|---|---|---:|']
        for sample in xadc.get('snapshots',[]):
            lines.append(f"| {sample['timestamp_local']} | {sample['phase']} | {sample['die_temperature_c']:.2f} |")
        lines += ['', 'These snapshots do not measure ambient temperature, total board watts or prior soak conditions.', '']
    else:
        lines += ['**Status: NOT MEASURED** — no verified Vivado XADC readings have been imported.',
                  'To capture readings, follow `docs/XADC_DIE_TEMPERATURE.md`. Estimated junction temperature is not a measurement.', '']
    lines+=['## Design-rule review (not waived)','',

        '| Rule | Severity | Instances |','|---|---|---:|']
    lines.extend(f"| {x['rule']} | {x['severity']} | {x['instances']} |" for x in s['drc_rules'])
    if not s['drc_rules']: lines.append('| no parsable rules | UNKNOWN | — |')
    lines+=['','## Physical reliability evidence (operator-observed)','',
        '| Phase | Jobs passed | Samples | FPGA identity | Evidence |',
        '|---|---:|---:|---|---|']
    for mode,item in s['physical_campaign'].items():
        lines.append(f"| {mode} | {item['passing_jobs']}/{item['total_jobs']} (failures={item['failed_jobs']}) | {_fmt(item['samples'])} | {item['bitstream_identity']} | `{item['source']}` ({item.get('evidence_type','unknown')}) |")
    if not s['physical_campaign']:lines.append('| Not recorded | — | — | — | — |')
    if s.get('physical_history'):
        lines += ['', '### Complete physical run history — do not erase failures', '',
                  '| Mode | Jobs PASS | Jobs FAIL | Evidence kind |',
                  '|---|---:|---:|---|']
        for run in s['physical_history']:
            lines.append(f"| {run.get('mode')} ({run.get('run_directory',run.get('date','?'))}) | {run.get('passed_jobs')} | {run.get('failed_jobs')} | {run.get('source_type','unknown')} |")
    q=s.get('media_quality_reference')
    if q:
        v=q.get('video',{}); au=q.get('audio',{})
        lines += ['', '## Integrated audiovisual quality — 3-second SOFTWARE REFERENCE run', '',
                  f"**Provenance:** {q.get('verification_provenance')}",
                  f"**Frames:** {v.get('input_frames')} | **Independent image stability:** {v.get('image_registration',{}).get('status','UNKNOWN')}",
                  f"**Crop retained area:** {v.get('crop',{}).get('area_retained_pct','N/A')}%", '',
                  '| Trajectory | High-frequency reduction |', '|---|---:|']
        for axis,val in v.get('high_frequency_motion_change_pct',{}).items():
            lines.append(f'| {axis.upper()} | {val}% |')
        lines += ['', '| Audio stage | 5–7.5 kHz change | 40–180 Hz change | 250–3000 Hz change |',
                  '|---|---:|---:|---:|']
        for key,val in au.get('band_power_relative_to_original_db',{}).items():
            lines.append(f"| {key} | {val.get('high_band_5_7k5_attenuation_db')} dB | {val.get('rumble_band_40_180_change_db')} dB | {val.get('speech_band_250_3000_change_db')} dB |")
        lines += ['', '**Caveat:** Image-content quality is inconclusive; audio band-power reduction does not prove intelligibility.']
    a=s['filter_reference_assessment']
    if a:
        lines+=['','## Numerical filter characterisation (MODEL ONLY)','',
                f"**Assessment status:** {a.get('status','UNKNOWN')} | **method:** {a.get('method','n/a')}",'',
                '| Bank | DC gain | -3 dB frequency | Band response |',
                '|---|---:|---:|---|']
        for name,b in a.get('filters',{}).items():
            lines.append(f"| {name} | {_fmt(b.get('dc_gain'))} | {_fmt(b.get('cutoff_3db_hz'),' Hz')} | {b.get('reference_bands','not available')} |")
    if s.get('current_gui_run'):
        m=s['current_gui_run']
        lines+=['','## Current GUI processing run','',
                f"- Mode: {'PHYSICAL FPGA bit-exact output' if m.get('hardware_verified') else 'SOFTWARE REFERENCE ONLY'}",
                f"- Video frames: {m.get('frames','NOT AVAILABLE')}",
                f"- Trajectory smoothing: X={m.get('x',{}).get('reduction_pct','?')}%, Y={m.get('y',{}).get('reduction_pct','?')}%, Roll={m.get('theta',{}).get('reduction_pct','?')}%",
                f"- Image stability: {m.get('image_stability',{}).get('status','NOT RUN')}",
                '']
    lines+=['','## Release limitations and pending sign-off','','']+['- '+item for item in s['limitations']]
    lines+=['','**Release level:** engineering demonstrator with recorded evidence, not industrial certification or real-time video/speech performance qualification.','']
    return '\n'.join(lines)

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'verification'/'system'/'generated')
    a=p.parse_args();result=collect()
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'engineering_summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (a.output/'engineering_summary.md').write_text(to_markdown(result),encoding='utf-8')
    print('ENGINEERING_SUMMARY_EXPORTED',a.output)
if __name__=='__main__':main()
#!/usr/bin/env python3
"""Conservative post-route report summary. Missing metrics stay UNKNOWN, never PASS."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def read(root, name):
    p = Path(root) / name
    return p.read_text(errors='replace') if p.exists() else ''

def timing(text):
    # This is the first numeric row below Vivado's Design Timing Summary header.
    match = re.search(r'Design Timing Summary.*?WNS\(ns\).*?\n\s*-[- ]+\s*\n\s*([^\n]+)', text, re.S)
    if not match: return {'setup_wns_ns': None, 'setup_tns_ns': None, 'hold_whs_ns': None, 'hold_ths_ns': None}
    values = re.findall(r'[-+]?\d+(?:\.\d+)?', match.group(1))
    if len(values) < 6: return {'setup_wns_ns': None, 'setup_tns_ns': None, 'hold_whs_ns': None, 'hold_ths_ns': None}
    return {'setup_wns_ns':float(values[0]),'setup_tns_ns':float(values[1]),'hold_whs_ns':float(values[4]),'hold_ths_ns':float(values[5])}

def used(text, label):
    m=re.search(r'^\|\s*'+re.escape(label)+r'\s*\|\s*([\d,]+)\s*\|',text,re.M)
    return int(m.group(1).replace(',','')) if m else None

def power(text):
    # Vivado revisions format Total On-Chip Power as NNN W or NNN (W).
    m=re.search(r'Total On-Chip Power\s*\(?W\)?\s*\|?\s*([\d.]+)', text, re.I)
    if not m: m=re.search(r'\|\s*Total On-Chip Power\s*\|\s*([\d.]+)\s*\|', text, re.I)
    if not m: m=re.search(r'Total On-Chip Power\s*:\s*([\d.]+)\s*W', text, re.I)
    return float(m.group(1)) if m else None

def drc_counts(text):
    # Results can be warning suggestions; do not label zero errors as all clear.
    violations=[]
    for m in re.finditer(r'^\|\s*([A-Z][A-Z0-9]+-\d+)\s*\|\s*(Error|Critical Warning|Warning)\s*\|[^\n]*?\|\s*(\d+)\s*\|\s*$', text, re.M):
        violations.append({'rule':m.group(1),'severity':m.group(2),'instances':int(m.group(3))})
    return violations

def analyze(root):
    ts=read(root,'timing_routed_final.rpt') or read(root,'timing_routed.rpt')
    ut=read(root,'utilization_routed_final.rpt') or read(root,'utilization_routed.rpt')
    dr=read(root,'drc_routed_final.rpt') or read(root,'drc_routed.rpt')
    pw=read(root,'power_routed_vectorless.rpt')
    t=timing(ts)
    u={'luts':used(ut,'Slice LUTs') or used(ut,'LUT as Logic'),
       'registers':used(ut,'Slice Registers'),
       'dsp48e1':used(ut,'DSP48E1 only'),
       'bram18':used(ut,'RAMB18'),
       'bonded_iobs':used(ut,'Bonded IOB')}
    # Some Vivado reports indent rows; parse indented memory/DSP rows separately.
    for key,pattern in [('dsp48e1','DSP48E1 only'),('bram18','RAMB18E1 only')]:
        if u[key] is None: u[key]=used(ut,pattern)
    violations=drc_counts(dr)
    passing = t['setup_wns_ns'] is not None and t['hold_whs_ns'] is not None and t['setup_tns_ns'] is not None and t['hold_ths_ns'] is not None and t['setup_wns_ns']>=0 and t['hold_whs_ns']>=0 and t['setup_tns_ns']>=0 and t['hold_ths_ns']>=0
    return {'scope':'post-route internal timing and static/vectorless estimation',
      'timing':t,'internal_timing_met':passing if ts else None,
      'resource_counts':u,'estimated_power_w':power(pw),'power_evidence':'vectorless Vivado estimate; NOT measured board watts' if pw else 'NOT AVAILABLE',
      'drc_report_present':bool(dr),'drc_rules':violations,
      'unconstrained_io_mentioned':bool(re.search(r'no_input_delay\s*\([1-9]|no_output_delay\s*\([1-9]|TIMING-18',ts)),
      'review_required':['Check external UART/reset constraints and DRC warnings even if internal timing is met.','Power is a scenario-dependent estimate, not measured supply current.','Cold/hot physical reliability requires separate board observations.']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--report-dir',required=True,type=Path);ap.add_argument('--json',type=Path,required=True);ap.add_argument('--markdown',type=Path,required=True)
    x=ap.parse_args();a=analyze(x.report_dir)
    x.json.parent.mkdir(parents=True,exist_ok=True);x.json.write_text(json.dumps(a,indent=2)+'\n')
    def fmt(v): return 'NOT AVAILABLE' if v is None else str(v)
    rows=['# FPGA maritime implementation — report triage','',f"Source report directory: `{x.report_dir}`",'',
       '| Metric | Result |','|---|---|']
    for k,v in a['timing'].items():rows.append(f'| {k} | {fmt(v)} |')
    rows.append(f"| Internal timing met (limited to existing constraints) | {fmt(a['internal_timing_met'])} |")
    for k,v in a['resource_counts'].items():rows.append(f'| {k} | {fmt(v)} |')
    rows.append(f"| Vectorless power estimate (W) | {fmt(a['estimated_power_w'])} |")
    rows += ['','## DRC rule details','','| Rule | Severity | Instances |','|---|---|---|']
    rows += [f"| {i['rule']} | {i['severity']} | {i['instances']} |" for i in a['drc_rules']]
    rows += ['','**Do not call this a complete timing, power or reliability sign-off.**','',*['- '+s for s in a['review_required']]]
    x.markdown.write_text('\n'.join(rows)+'\n');print(json.dumps(a,indent=2))

if __name__=='__main__': main()

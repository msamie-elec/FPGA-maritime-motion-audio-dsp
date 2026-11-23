"""Host-only self-test for the additional engineering qualification tools."""
import csv
import importlib.util
import io
import json
import sys
from pathlib import Path

def load_module(name, filename):
    path=Path(__file__).resolve().parents[3]/('verification/system' if filename=='maritime_reliability.py' else 'scripts')/filename
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj
    spec.loader.exec_module(obj)
    return obj

def test_report_parser_exposes_missing_power_and_warnings(tmp_path):
    report=load_module('final_report_parser','summarize_release_reports.py')
    d=tmp_path
    (d/'timing_routed.rpt').write_text('''Design Timing Summary\n\n WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints\n -------- -------- -------- -------- -------- --------\n  0.916  0.000  0  2704  0.034 0.000 0 2704\nno_input_delay (2)''')
    (d/'utilization_routed.rpt').write_text('| Slice LUTs | 630 | 0 | 0 | 20800 | 3.03 |\n| Slice Registers | 856 | 0 | 0 | 41600 | 2.06 |')
    (d/'drc_routed.rpt').write_text('| REQP-1840 | Warning | RAMB18 async control check | 2 |')
    p=report.analyze(d)
    assert p['timing']['setup_wns_ns']==0.916
    assert p['timing']['hold_whs_ns']==0.034
    assert p['resource_counts']['luts']==630
    assert p['estimated_power_w'] is None
    assert p['drc_rules'][0]['instances']==2
    assert p['unconstrained_io_mentioned']

def test_physical_reliability_case_suite_and_failures_recorded(tmp_path,monkeypatch):
    # Import host reference and protocol from the installed project root.
    import pathlib
    host=str(pathlib.Path(__file__).resolve().parents[3]/'host')
    if host not in sys.path:sys.path.insert(0,host)
    reliability=load_module('maritime_reliability_tool','maritime_reliability.py')
    samples=reliability.make_cases(5,55)
    assert len(samples)==4 and len(samples[1][2])==512
    def fake_hardware(port,samples,job_id):
        from fixed_point_golden import FirReference,load_coefficients
        from design_audio_coefficients import design
        coeffs=design() if job_id&0x80 else load_coefficients()
        return FirReference(coeffs).process(samples)
    monkeypatch.setattr(reliability,'run_batch',fake_hardware)
    target=tmp_path/'cases.csv'
    with target.open('w',newline='') as fd:
        w=csv.DictWriter(fd,fieldnames=reliability.FIELDS);w.writeheader()
        rows=reliability.run_set('MOCK-NOT-PHYSICAL','warm',1,0,55,w,fd,'TEST ONLY')
    assert len(rows)==4 and all(r['passed'] for r in rows)
    monkeypatch.setattr(reliability,'run_batch',lambda *args,**kwargs: (_ for _ in ()).throw(TimeoutError('fake timeout')))
    with target.open('a',newline='') as fd:
        w=csv.DictWriter(fd,fieldnames=reliability.FIELDS)
        failed=reliability.run_set('MOCK-NOT-PHYSICAL','warm',2,0,55,w,fd,'TEST ONLY')
    assert len(failed)==4 and all(not r['passed'] for r in failed)
    assert 'TimeoutError' in failed[0]['exception']
    assert len(list(csv.DictReader(target.open())))==8

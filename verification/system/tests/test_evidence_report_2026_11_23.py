"""No clean retest may hide an earlier failed trial; no old reference may replace RevD."""
from pathlib import Path
import sys, json
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from engineering_summary import collect,to_markdown

def test_latest_owner_uploaded_revd_not_old_reference():
    d=collect(ROOT)
    assert d['timing']['setup_wns_ns']==1.74
    assert d['timing']['hold_whs_ns']==0.046
    assert d['resources']['luts']==632
    assert d['estimated_power_w']==0.071
    assert d['report_source_type'].startswith('OWNER UPLOADED')
    assert all(x['rule'] not in ('REQP-1840','CFGBVS-1') for x in d['drc_rules'])

def test_reliability_history_including_failure_preserved():
    s=collect(ROOT)
    assert s['physical_campaign']['reset']['passing_jobs']==80
    assert s['physical_campaign']['cold']['passing_jobs']==40
    assert s['physical_campaign']['soak']['passing_jobs']==4408
    fails=[x for x in s['physical_history'] if x['mode']=='soak' and x['failed_jobs']]
    assert fails and fails[0]['failed_jobs']==141
    out=to_markdown(s)
    assert '141' in out and '4408' in out
    assert 'SOFTWARE REFERENCE ONLY' in out
    assert 'INCONCLUSIVE' in out

def test_no_new_hardware_source_or_second_vivado_project():
    assert len(list(ROOT.rglob('*.xpr')))==1
    assert (ROOT/'hardware/build/maritime_a7.xpr').is_file()
    assert (ROOT/'docs/MEDIA_QUALITY_2026-11-23.md').is_file()

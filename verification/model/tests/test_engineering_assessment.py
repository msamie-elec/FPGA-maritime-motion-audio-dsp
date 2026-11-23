"""Industrial-style numerical regression: never re-label analytic tests as board proof."""
from __future__ import annotations
import importlib.util
import sys
import re
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]

def module(name,file):
    spec=importlib.util.spec_from_file_location(name,file)
    obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj
    spec.loader.exec_module(obj)
    return obj

def test_software_filter_model(tmp_path):
    m=module('industrial_filter_assessment',ROOT/'verification/model/industrial_filter_assessment.py')
    res=m.run(tmp_path,plot=False)
    assert res['status']=='PASS MODEL INVARIANTS'
    assert set(res['filters'])=={'motion','audio'}
    assert res['filters']['motion']['dc_gain']==1.0
    assert res['filters']['audio']['dc_gain']==1.0
    assert all(d['max_integer_model_error_lsb']==0 for d in res['filters'].values())
    assert res['filters']['motion']['stopband_worst_db'] < -10
    assert res['filters']['audio']['stopband_worst_db'] < -10
    assert (tmp_path/'audio_frequency_response.csv').exists()
    assert 'not HDL' in res['evidence_level']

def test_summary_provenance_and_missing_evidence(tmp_path):
    m=module('engineering_summary',ROOT/'host/engineering_summary.py')
    none=m.collect(tmp_path)
    assert none['report_provenance'] is None
    assert none['estimated_power_w'] is None
    assert not none['internal_timing_met']
    assert not none['physical_campaign']
    base=tmp_path/'evidence'/'reference_2026-11-20';base.mkdir(parents=True)
    (base/'report_summary.json').write_text(json.dumps({'timing':{'setup_wns_ns':0.9},'resource_counts':{'luts':630},
          'estimated_power_w':0.071,'internal_timing_met':True,'unconstrained_io_mentioned':True,'drc_rules':[{'rule':'REQP-1840','severity':'Warning','instances':1}]}))
    snap=m.collect(tmp_path)
    assert snap['historical_baseline'] is True
    assert snap['timing']['setup_wns_ns']==0.9
    text=m.to_markdown(snap)
    assert 'ARCHIVED' in text and 'REQP-1840' in text
    assert '0.071 W' in text

def test_portable_native_xpr_and_simulation_sources():
    p=ROOT/'hardware'/'build'/'maritime_a7.xpr'
    project=ET.parse(p).getroot()
    files=[e.attrib['Path'] for e in project.iter('File') if 'Path' in e.attrib]
    assert 'xc7a35ticsg324-1L' in p.read_text()
    assert '$PPRDIR/../sim/tb/tb_maritime_uart_top.sv' in files
    assert '$PPRDIR/../sim/tb/tb_fir_sequential.sv' in files
    assert all(re.match(r'^[A-Za-z]:[/\\]', f) is None and '$PPRDIR/../' in f for f in files)
    assert project.attrib['Path']=='maritime_a7.xpr'
    for f in files: assert (ROOT/'hardware'/'build'/f.replace('$PPRDIR/','')).resolve().exists()


def test_single_xpr_and_three_distinct_verification_levels():
    assert len(list(ROOT.rglob('*.xpr'))) == 1
    assert (ROOT/'hardware/build/maritime_a7.xpr').is_file()
    assert (ROOT/'hardware/sim/tb/tb_reset_sync.sv').is_file()
    assert (ROOT/'verification/model/industrial_filter_assessment.py').is_file()
    assert (ROOT/'verification/system/maritime_reliability.py').is_file()
    assert not (ROOT/'rtl').exists()
    assert not (ROOT/'tb').exists()
    assert not (ROOT/'build/vivado_maritime_a7').exists()

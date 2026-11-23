"""RevI XADC evidence: provenance and summary integrity."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from engineering_summary import read_xadc,collect,to_markdown

def test_supplied_xadc_evidence_and_summary():
    data=read_xadc(ROOT)
    assert data['status']=='MEASURED'
    assert data['count']==36
    assert data['min_c']==31.6
    assert data['max_c']==32.4
    assert data['latest_c']==32.2
    assert data['by_phase']['idle']['n']==14
    assert data['by_phase']['post_processing']['n']==20
    assert data['by_phase']['soak_end']['n']==2
    assert 'Vivado' not in str(data['by_phase'])
    s=to_markdown(collect(ROOT))
    assert '36' in s and '32.4' in s and 'soak_end' in s
    assert 'not backed by a confirmed soak' in s

def test_source_archive_fallback_is_explicit(tmp_path):
    import shutil
    target=tmp_path/'evidence/xadc_2026-11-23/xadc_snapshots.csv'
    target.parent.mkdir(parents=True)
    shutil.copy(ROOT/'evidence/xadc_2026-11-23/xadc_snapshots.csv',target)
    data=read_xadc(tmp_path)
    assert data['status']=='MEASURED'
    assert data['source_type']=='ARCHIVED_OPERATOR_CSV'
    assert data['latest_c']==32.2

def test_no_measurement_without_csv(tmp_path):
    assert read_xadc(tmp_path)['status']=='NOT_MEASURED'

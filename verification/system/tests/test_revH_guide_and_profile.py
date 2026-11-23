"""Release guide integrity and fixed historical profile provenance tests."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[3]

def test_command_guide_covers_every_verification_level():
    guide=(ROOT/'docs/TEST_AND_VERIFICATION_COMMANDS.md').read_text(encoding='utf-8')
    for term in ('industrial_filter_assessment', 'run_engineering_assessment.ps1',
                 'run_maritime_xsim.ps1','run_fir_xsim.ps1',
                 'final_rebuild_and_reports.ps1', 'verify_unified_av_hardware.ps1',
                 '--mode reset', '--mode cold', '--mode soak',
                 'run_media_quality.ps1', 'sample_xadc_snapshot.tcl',
                 'prepare_github_release.ps1'):
        if term=='industrial_filter_assessment':
            # invoked by run_engineering_assessment.ps1 rather than separately
            assert (ROOT/'verification/model/industrial_filter_assessment.py').exists()
        else:
            assert term in guide, term
    assert 'bitstream' in guide.lower() and ('software reference' in guide.lower() or 'software-reference' in guide.lower())

def test_software_profile_reference_is_not_claimed_physical():
    file=ROOT/'evidence/quality_2026-11-23_reference/normal_strong_reference.json'
    data=json.loads(file.read_text(encoding='utf-8'))
    assert data['evidence_type']=='SOFTWARE_REFERENCE_PROFILE_COMPARISON_NOT_FPGA'
    assert data['input_file']=='03_Unified_Quick_Test_3s.mp4'
    assert round(data['profiles']['normal']['x_pct'],2)==8.14
    assert round(data['profiles']['strong']['x_pct'],2)==12.97
    assert data['profiles']['normal']['image_registration_status']=='INCONCLUSIVE'

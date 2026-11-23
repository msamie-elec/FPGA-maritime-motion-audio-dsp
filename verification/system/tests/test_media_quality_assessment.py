"""Engineering scope/provenance guardrails for quantitative end-to-end analysis."""
from __future__ import annotations
import json, sys, wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'verification/system'))
from media_quality_assessment import assess, to_markdown

def wav(path, samples):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(np.asarray(samples,dtype='<i2').tobytes())

def test_assessment_is_provenance_safe_and_uses_audio_stages(tmp_path):
    metrics={'source_video':'test.mp4','frames':90,'hardware_verified':False,
             'x':{'reduction_pct':8.138},'y':{'reduction_pct':5.99},'theta':{'reduction_pct':5.01},
             'crop':{'area_retained_pct':92.46},
             'image_stability':{'status':'INCONCLUSIVE','reason':'low texture'}}
    (tmp_path/'metrics.json').write_text(json.dumps(metrics))
    samples=(np.sin(np.arange(16000)*2*np.pi*250/16000)*10000).astype('int16')
    wav(tmp_path/'audio_original.wav',samples)
    wav(tmp_path/'audio_fir_only.wav',samples//2)
    wav(tmp_path/'audio_filtered.wav',samples//3)
    a=assess(tmp_path)
    assert a['verification_provenance'].startswith('SOFTWARE REFERENCE')
    assert a['video']['image_registration']['status']=='INCONCLUSIVE'
    assert a['video']['high_frequency_motion_change_pct']['x']==8.138
    assert a['audio']['stages']['original']['samples']==16000
    assert set(a['audio']['band_power_relative_to_original_db'])=={'fpga_compatible_fir','final_hybrid'}
    assert 'not verified' not in to_markdown(a).lower() or 'SOFTWARE' in to_markdown(a)

def test_no_unearned_hardware_or_perceptual_claims(tmp_path):
    (tmp_path/'metrics.json').write_text(json.dumps({'frames':22,'hardware_verified':False,
        'image_stability':{'status':'INCONCLUSIVE'}}))
    x=assess(tmp_path)
    assert x['audio']['status']=='NOT AVAILABLE'
    assert x['video']['claim'].endswith('NOT ESTABLISHED')
    assert 'intelligibility' in ' '.join(x['limitations'])

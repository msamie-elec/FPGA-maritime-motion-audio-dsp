"""Compare video-stabilisation strengths WITHOUT using an FPGA.

Runs the same image input through two distinct software-reference 17-tap FIR
passes. Trajectory reduction != proven visual stability. Cropping is explicit.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from gui_pipeline import run_pipeline
from processing_control import checkpoint, progress as notify

PROFILE_NAMES = ('Normal', 'Strong')

def compare_profiles(source: Path, trajectory: Path | None, output_dir: Path,
                     *, cancel_event=None, progress=None) -> dict:
    source = Path(source)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = {}
    for i, profile in enumerate(PROFILE_NAMES):
        checkpoint(cancel_event)
        notify(progress, 'profile_compare', i, len(PROFILE_NAMES))
        result = run_pipeline(source, trajectory, output_dir/profile.lower(), None,
                              profile=profile, cancel_event=cancel_event)
        m=result.metrics
        profiles[profile.lower()] = {
            'x_pct': float(m['x']['reduction_pct']),
            'y_pct': float(m['y']['reduction_pct']),
            'roll_pct': float(m.get('theta', {}).get('reduction_pct', 0)),
            'crop_area_retained_pct': float(m.get('crop',{}).get('area_retained_pct',100.)),
            'image_registration_status': m.get('image_stability',{}).get('status','UNKNOWN'),
            'image_registration_reduction_pct': m.get('image_stability',{}).get('reduction_pct'),
            'motion_estimation_warnings': m.get('motion_quality_warnings',[]),
            'report_directory': profile.lower(),
        }
        notify(progress, 'profile_compare', i+1, len(PROFILE_NAMES))
    normal=profiles['normal']; strong=profiles['strong']
    stronger = all(strong[k]>=normal[k] for k in ('x_pct','y_pct','roll_pct'))
    visually_verified = (strong['image_registration_status']=='MEASURED'
                         and normal['image_registration_status']=='MEASURED')
    status = 'STRONG_NUMERICALLY_SMOOTHER' if stronger else 'MIXED_TRAJECTORY_EFFECT'
    message = ('Strong reduces measured trajectory jitter more, at the stated crop cost. '
               'Independent image assessment must be considered separately.' if stronger
               else 'Profiles have mixed trajectory behaviour. Inspect the independent image assessment.')
    result = {
        'evidence_type':'SOFTWARE_REFERENCE_PROFILE_COMPARISON_NOT_FPGA',
        'input_file':source.name,
        'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'status':status,
        'independent_image_proxy_favors_strong':bool(visually_verified and
            strong['image_registration_reduction_pct'] is not None and
            normal['image_registration_reduction_pct'] is not None and
            strong['image_registration_reduction_pct']>normal['image_registration_reduction_pct']),
        'profiles':profiles,'interpretation':message,
        'limitations': 'Camera pose inferred from optical flow; moving water or vessels may dominate. '
                       'No FPGA computations are used. Compare videos and examine crop before choosing a profile.',
    }
    (output_dir/'profile_comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    lines=['# Normal vs Strong — software reference comparison','',
        f'Input: `{source.name}`',f'Source SHA-256: `{result["input_sha256"]}`','',
        '| Metric | Normal | Strong |','|---|---:|---:|']
    for label,key,suffix in [('X high-frequency reduction','x_pct','%'),('Y high-frequency reduction','y_pct','%'),
                             ('Roll high-frequency reduction','roll_pct','%'),('Crop retained area','crop_area_retained_pct','%')]:
        lines.append(f'| {label} | {normal[key]:.2f}{suffix} | {strong[key]:.2f}{suffix} |')
    lines += ['','Independent image registration: '+normal['image_registration_status']+
              ' / '+strong['image_registration_status'],'',message,'',result['limitations'],'']
    (output_dir/'profile_comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    return result

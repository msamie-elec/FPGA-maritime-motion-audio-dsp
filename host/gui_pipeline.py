"""Reusable hardware-backed GUI pipeline (no GUI imports).

Everything measured as 'physical FPGA' must pass the bit-exact reference
comparison implemented in stabilize_video.smooth_trajectory().
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import json, time, shutil
from motion_estimation import inspect_video
from motion_estimation_v07 import estimate_three_axis
from affine_stabilization import stabilise_affine
from generate_synthetic_clip import generate
from stabilize_video import stabilize, inputs_from_csv
from export_results import export_result_files
from image_stability import compare_image_stability


@dataclass
class ProcessingResult:
    video: Path
    trajectory: Path
    side_by_side: Path
    metrics: dict
    filtered_trajectory: dict
    estimation: dict
    elapsed_s: float
    output_dir: Path


def prepare_video(video: Path | None, trajectory: Path | None, output_dir: Path) -> tuple[Path, Path, dict]:
    output_dir.mkdir(parents=True,exist_ok=True)
    if video is None:
        v,t = generate(output_dir, duration=5.0, fps=30)
        info=inspect_video(v)
        return v,t,{'method':'known_synthetic_ground_truth','frames':info.frames,'fps':info.fps}
    video=Path(video)
    info=inspect_video(video)
    if trajectory:
        trajectory=Path(trajectory)
        if not trajectory.is_file():raise ValueError('Selected trajectory CSV not found')
        x,y=inputs_from_csv(trajectory)
        if len(x)!=info.frames or len(y)!=info.frames:
            raise ValueError(f'Trajectory CSV has {len(x)} rows but video has {info.frames} frames.')
        return video,trajectory,{'method':'user_supplied_trajectory_csv','frames':info.frames,'fps':info.fps}
    target=output_dir/'estimated_camera_trajectory.csv'
    meta=estimate_three_axis(video,target,output_dir/'motion_estimation_diagnostics.json')
    return video,target,meta


def run_pipeline(video: Path | None, trajectory: Path | None, output_dir: Path, port: str | None, profile: str = "Normal") -> ProcessingResult:
    start=time.monotonic()
    v,t,est=prepare_video(video,trajectory,output_dir)
    output,metrics=(stabilise_affine(v,t,output_dir,port=port,profile=profile)
                    if video is not None and trajectory is None
                    else stabilize(v,t,output_dir,port=port))
    filtered=json.loads((output_dir/'filtered_trajectory.json').read_text())
    metrics['estimation']=est
    metrics['filter_profile']=profile if video is not None and trajectory is None else 'Legacy FIR'
    metrics['motion_quality_warnings']=est.get('warnings',[]) 
    metrics['image_stability']=compare_image_stability(output)
    q=metrics['image_stability']
    metrics['visual_outcome']=(
        'IMPROVED' if q.get('status')=='MEASURED' and q.get('reduction_pct',0)>0 else
        'WORSE' if q.get('status')=='MEASURED' else 'INCONCLUSIVE')
    metrics['input_type']='SYNTHETIC_KNOWN_MOTION' if video is None else ('USER_SUPPLIED_TRAJECTORY_BENCH_TEST' if trajectory is not None else 'AUTO_ESTIMATION_NO_INJECTED_MOTION')
    # Preserve the original-recording SHA and zero-injection provenance in every run.
    manifest=v.parent/(v.stem+'_source_provenance.json')
    if manifest.exists():
        evidence=json.loads(manifest.read_text(encoding='utf-8'))
        metrics['source_provenance']={k:evidence.get(k) for k in ('source_kind','source_sha256','injected_motion','operations','clip_start_s','clip_duration_s')}
        shutil.copyfile(manifest, output_dir/'source_provenance.json')
    metrics['end_to_end_wall_s']=round(time.monotonic()-start,3)
    metrics['hardware_verified']=(port is not None and metrics['mode']=='PHYSICAL FPGA - BIT-EXACT VERIFIED')
    (output_dir/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
    export_result_files(t, filtered, metrics, output_dir)
    return ProcessingResult(video=v,trajectory=t,side_by_side=output,metrics=metrics,
                            filtered_trajectory=filtered,estimation=est,
                            elapsed_s=metrics['end_to_end_wall_s'],output_dir=output_dir)

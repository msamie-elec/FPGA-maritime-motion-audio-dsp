#!/usr/bin/env python3
"""Stage-labelled, repeatable quality analysis of an existing full-system media run.

Does not process FPGA hardware or infer image quality from FIR arithmetic alone.
Inputs are pipeline-produced metrics.json and WAVs. Refuses to invent ground truth
SNR, speech intelligibility, real scene stability or an FPGA verification claim.
"""
from __future__ import annotations
import argparse, json, math, hashlib, sys, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'host'))
from audio_dsp import analyze, FS

def load_wav(path: Path):
    with wave.open(str(path), 'rb') as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getframerate()!=FS:
            raise ValueError(f'Expected mono 16-kHz 16-bit WAV: {path}')
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').copy()

def audio_stats(samples):
    x=np.asarray(samples,dtype=np.float64)
    return {'samples':len(x), 'rms_pcm':round(float(np.sqrt(np.mean(x*x))),3),
            'peak_pcm':int(np.max(np.abs(x))) if len(x) else None,
            'clip_fraction_pct':round(100*float(np.mean(np.abs(x)>=32767)),6)}

def _safe_pct(x):
    return round(float(x),3) if x is not None and math.isfinite(float(x)) else None

def assess(run_dir:Path):
    run_dir=Path(run_dir).resolve()
    metrics_path=run_dir/'metrics.json'
    if not metrics_path.is_file(): raise FileNotFoundError(metrics_path)
    m=json.loads(metrics_path.read_text(encoding='utf-8'))
    source=m.get('source_video') or m.get('source') or 'UNKNOWN'
    physical=bool(m.get('combined_hardware_verified',m.get('hardware_verified',False)))
    video={
      'input_frames':m.get('frames'), 'source':source,
      'computation': 'PHYSICAL-FPGA FIR + HOST WARP' if physical else 'SOFTWARE-REFERENCE FIR + HOST WARP',
      'high_frequency_motion_change_pct':{},
      'image_registration':m.get('image_stability',{'status':'NOT MEASURED'}),
      'crop':m.get('crop',{}),
      'claim':'independent image-movement reduction NOT ESTABLISHED',
    }
    for axis in ('x','y','theta'):
        a=m.get(axis,{})
        video['high_frequency_motion_change_pct'][axis]=_safe_pct(a.get('reduction_pct'))
    if video['image_registration'].get('status') == 'MEASURED':
        video['claim']='image-motion proxy measured; NOT a ground-truth camera-pose or subjective improvement claim'
    names={'original':'audio_original.wav','fpga_compatible_fir':'audio_fir_only.wav','final_hybrid':'audio_filtered.wav'}
    wavs={k:load_wav(run_dir/v) for k,v in names.items() if (run_dir/v).is_file()}
    audio={'status':'NOT AVAILABLE','physical_fir_verified':physical,'stages':{},'band_power_relative_to_original_db':{},
           'interpretation':'Band energy change does not establish intelligibility, isolated SNR or perceived quality.'}
    if 'original' in wavs:
        n=len(wavs['original'])
        if any(len(x)!=n for x in wavs.values()):raise ValueError('Different WAV lengths; cannot compare')
        audio['status']='MEASURED';audio['source_samples']=n
        audio['stages']={name:audio_stats(x) for name,x in wavs.items()}
        audio['band_power_relative_to_original_db']={name:analyze(wavs['original'],x)
                        for name,x in wavs.items() if name!='original'}
        audio['stage_sha256']={k:hashlib.sha256((run_dir/names[k]).read_bytes()).hexdigest()
                                for k in wavs}
    return {'assessment':'END_TO_END_MEDIA_PROXY_METRICS','source_run':str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else run_dir.name,
            'source_metrics_sha256':hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
            'verification_provenance':'PHYSICAL FPGA FIR verified in pipeline' if physical else 'SOFTWARE REFERENCE ONLY; do not claim this run used FPGA',
            'video':video,'audio':audio,
            'limitations':['No clean ground-truth reference audio; no measured speech intelligibility/SNR.',
                           'Audio bands mix wanted speech and unwanted noise.',
                           'Trajectory smoothing is not a substitute for independent image-content stability.',
                           'Image registration can be INCONCLUSIVE for low-texture or moving-scene footage.',
                           'Host performs frame warping, final encoding and adaptive audio stage.']}

def to_markdown(s):
    v=s['video'];a=s['audio']; lines=[
      '# Maritime audiovisual performance assessment','',
      f"**Run:** `{s['source_run']}`", f"**Provenance:** {s['verification_provenance']}",'',
      '## Video: motion and independent image stability','',
      '| Measure | Result |','|---|---:|',
      f"| Frames | {v['input_frames']} |",]
    for ax,val in v['high_frequency_motion_change_pct'].items():
        lines.append(f'| High-frequency {ax.upper()} trajectory reduction | {val if val is not None else "N/A"}% |')
    st=v['image_registration']
    lines.extend([f"| Independent image stability | {st.get('status','UNKNOWN')} |",
       f"| Crop retained area | {v.get('crop',{}).get('area_retained_pct','N/A')}% |",'',
       f"**Interpretation:** {v['claim']}. {st.get('reason','')}",'',
       '## Audio: stage-resolved measured band power','',
       '| Stage | 5–7.5 kHz change | 40–180 Hz change | 250–3000 Hz change |','|---|---:|---:|---:|'])
    keys=('high_band_5_7k5_attenuation_db','rumble_band_40_180_change_db','speech_band_250_3000_change_db')
    for k,m in a['band_power_relative_to_original_db'].items():
        lines.append('| '+k+' | '+' | '.join(str(m.get(c,'N/A'))+' dB' for c in keys)+' |')
    lines.extend(['','**Audio interpretation:** '+a['interpretation'],'',
      '## Qualifications','',*('- '+l for l in s['limitations']),''])
    return '\n'.join(lines)

def plot(s,out_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:return []
    out=[]; bands=[('5–7.5 kHz','high_band_5_7k5_attenuation_db'),('40–180 Hz','rumble_band_40_180_change_db'),('250–3000 Hz','speech_band_250_3000_change_db')]
    audio=s['audio']['band_power_relative_to_original_db']
    if audio:
        fig,ax=plt.subplots(figsize=(9,4.6)); names=list(audio); x=np.arange(len(bands));width=.8/max(1,len(names))
        for i,name in enumerate(names):
            vals=[audio[name].get(k) for _,k in bands]
            ax.bar(x+(i-(len(names)-1)/2)*width,[v or 0 for v in vals],width,label=name)
        ax.set_xticks(x,[n for n,_ in bands]);ax.set_ylabel('Band-power change from original (dB)')
        ax.set_title('Measured audio spectrum changes: not intelligibility or isolated SNR')
        ax.axhline(0,linewidth=.6);ax.legend();fig.tight_layout()
        path=out_dir/'audio_stage_band_changes.png';fig.savefig(path,dpi=150);plt.close(fig);out.append(path)
    v=s['video']['high_frequency_motion_change_pct']
    if all(x is not None for x in v.values()):
        fig,ax=plt.subplots(figsize=(8,3.8));ax.bar(list(v),list(v.values()))
        ax.set_title('High-frequency motion trajectory smoothing (not verified image stability)')
        ax.set_ylabel('Reduction in high-frequency RMS (%)');ax.axhline(0,linewidth=.6)
        fig.tight_layout();path=out_dir/'trajectory_reduction.png';fig.savefig(path,dpi=150);plt.close(fig);out.append(path)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--out',type=Path)
    a=p.parse_args();out=(a.out or a.run_dir);out.mkdir(parents=True,exist_ok=True)
    data=assess(a.run_dir)
    (out/'quality_assessment.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (out/'quality_assessment.md').write_text(to_markdown(data),encoding='utf-8')
    imgs=plot(data,out)
    print('MEDIA_QUALITY_ASSESSMENT_COMPLETE', out, '\n'.join(map(str,imgs)))
if __name__=='__main__':main()

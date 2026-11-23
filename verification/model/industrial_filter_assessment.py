#!/usr/bin/env python3
"""FIR numerical engineering characterisation, not a claim of FPGA execution.

Compares mathematical convolution with bit-exact integer model, documents
frequency response, pass/stop bands, DC and quantisation/overflow edge cases.
The FPGA/RTL equivalence is established by separate HDL & physical test runs.
"""
from __future__ import annotations
import argparse,csv,json,math,hashlib,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'host'))
from fixed_point_golden import FirReference,load_coefficients,SAMPLE_MAX,SAMPLE_MIN
from design_audio_coefficients import design as audio_design

CONFIG={
    'motion': {'fs':30.0,'passband':(0.0,1.0),'stopband':(6.0,15.0),'probe':(0.3,8.0),'units':'Hz at 30 fps'},
    'audio': {'fs':16000.0,'passband':(0.0,2000.0),'stopband':(5000.0,8000.0),'probe':(500.0,6500.0),'units':'Hz at 16 kHz'},
}

def response(coeffs,fs):
    freq=np.linspace(0,fs/2,1025)
    tap=np.arange(len(coeffs),dtype=float)
    H=np.exp(-2j*np.pi*freq[:,None]*tap[None,:]/fs) @ (np.asarray(coeffs,dtype=float)/(2**15))
    mag=np.abs(H); db=20*np.log10(np.maximum(mag,1e-14))
    return freq,mag,db

def characterize(name,coeffs):
    cfg=CONFIG[name];fs=cfg['fs']; f,mag,db=response(coeffs,fs)
    dc=sum(coeffs)/(2**15)
    pass_sel=(f>=cfg['passband'][0])&(f<=cfg['passband'][1]);stop_sel=(f>=cfg['stopband'][0])&(f<=cfg['stopband'][1])
    # interpolation where the first -3dB crossing occurs; not a design requirement.
    idx=np.flatnonzero(db<=-3.0103);cross=None
    if len(idx) and idx[0]>0:
        i=int(idx[0]); cross=float(np.interp(-3.0103,[db[i],db[i-1]],[f[i],f[i-1]]))
    rng=np.random.default_rng(20261121 if name=='motion' else 20261122)
    cases={
       'impulse':[32768]+[0]*64,
       'positive_dc':[32768]*80,
       'negative_dc':[-32768]*80,
       'zeros':[0]*80,
       'mixed_edges':[SAMPLE_MAX,SAMPLE_MIN,0,1,-1]*20,
       'random_fullscale':rng.integers(SAMPLE_MIN,SAMPLE_MAX+1,size=512,dtype=np.int64).tolist(),
    }
    total=0; failed=[]; saturated=0; max_lsb=0
    # Independent signed integer convolution with explicit negative-floor shift and saturation.
    for tag,vectors in cases.items():
        ref=FirReference(coeffs); actual=ref.process(vectors);total+=len(vectors)
        for i,(v,got) in enumerate(zip(vectors,actual)):
            acc=sum(int(vectors[i-t])*int(coeffs[t]) for t in range(min(i,len(coeffs)-1)+1))
            expected=max(SAMPLE_MIN,min(SAMPLE_MAX,acc//(2**15)))
            saturated+=int(expected in (SAMPLE_MIN,SAMPLE_MAX))
            max_lsb=max(max_lsb,abs(expected-got))
            if expected!=got:failed.append([tag,i,expected,got])
    # sine attenuation corroborates full coefficient frequency response using
    # fixed-point model, discarding warm-up to avoid startup transients.
    sine=[]
    for freq in cfg['probe']:
        N=4096; xx=np.arange(N,dtype=float)
        amp=240000
        samples=[int(round(amp*math.sin(2*math.pi*freq*n/fs))) for n in xx]
        yy=np.asarray(FirReference(coeffs).process(samples),dtype=float)
        offset=len(coeffs)+150
        inp=np.asarray(samples[offset:],dtype=float);out=yy[offset:]
        # RMS amplitude attenuation (sine amplitude matters in transition bands).
        v1=float(np.sqrt(np.mean(inp*inp)));v2=float(np.sqrt(np.mean(out*out)))
        measured_db=float(20*math.log10(max(v2,1e-15)/max(v1,1e-15)))
        theoretical=20*math.log10(max(abs(sum(c/(2**15)*np.exp(-2j*np.pi*freq*k/fs) for k,c in enumerate(coeffs))),1e-15))
        sine.append({'frequency_hz':freq,'fixed_point_rms_gain_db':round(measured_db,3),'theoretical_gain_db':round(theoretical,3)})
    return {'bank':name,'fs_hz':fs,'taps':len(coeffs),'sum_coeff_q15':sum(coeffs),
            'coefficient_sha256':hashlib.sha256( ('\n'.join(str(x) for x in coeffs)+'\n').encode()).hexdigest(),
            'symmetric':list(coeffs)==list(reversed(coeffs)),
            'dc_gain':round(dc,8),'cutoff_3db_hz':round(cross,3) if cross else None,
            'passband_hz':list(cfg['passband']), 'passband_min_db':round(float(min(db[pass_sel])),3),
            'passband_max_db':round(float(max(db[pass_sel])),3),
            'stopband_hz':list(cfg['stopband']),'stopband_worst_db':round(float(max(db[stop_sel])),3),
            'reference_bands':f"0–{cfg['passband'][1]:g} Hz pass, {cfg['stopband'][0]:g}–{cfg['stopband'][1]:g} Hz assessed stop",
            'fixed_point_samples_checked':total,'max_integer_model_error_lsb':max_lsb,
            'saturated_output_count':saturated,'mismatches':failed[:10],
            'sine_probes':sine}, (f,db)

def run(out,plot=True):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    banks={'motion':load_coefficients(),'audio':audio_design()}
    data={'status':'PASS MODEL INVARIANTS' ,'method':'Float FFT of signed Q1.15 coefficients + independent integer convolution against fixed-point Python model',
          'evidence_level':'ANALYTIC / SOFTWARE ONLY — not HDL, not physical FPGA, not perceptual-quality validation',
          'filters':{},'gates':{},'warnings':['Sine response for a linear time-invariant FIR does not establish actual speech enhancement or camera stabilization.']}
    for name,coeff in banks.items():
        x,(freq,db)=characterize(name,coeff);data['filters'][name]=x
        good=(len(coeff)==17 and x['symmetric'] and x['sum_coeff_q15']==32768 and x['max_integer_model_error_lsb']==0)
        data['gates'][name+'_fixed_point_invariants']=bool(good)
        with (out/(name+'_frequency_response.csv')).open('w',newline='') as h:
            w=csv.writer(h);w.writerow(['frequency_hz','model_gain_db'])
            w.writerows(zip(freq,np.around(db,6)))
        if plot:
            import matplotlib
            matplotlib.use('Agg')
            from matplotlib import pyplot as plt
            plt.figure(figsize=(9,4.5));plt.plot(freq,db);plt.ylim(-120,5)
            plt.axhline(-3.0103,ls='--',lw=1);plt.grid(alpha=.3)
            plt.title(f'{name.capitalize()} 17-tap FIR — coefficient model (not physical measurement)')
            plt.xlabel('Frequency (Hz)');plt.ylabel('Magnitude (dB)')
            plt.tight_layout();plt.savefig(out/(name+'_frequency_response.png'),dpi=130);plt.close()
    data['status']='PASS MODEL INVARIANTS' if all(data['gates'].values()) else 'FAIL MODEL INVARIANTS'
    (out/'filter_assessment.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    md=['# Filter engineering assessment','',
        '**Evidence class: Analytical filter model, not Vivado XSim and not measured FPGA results.**','',
        '| Bank | DC gain | -3 dB Hz | Passband min/max (dB) | Worst stopband gain (dB) | Integer-model comparison |',
        '|---|---:|---:|---|---:|---:|']
    for name,d in data['filters'].items():
        md.append(f"| {name} | {d['dc_gain']} | {d['cutoff_3db_hz']} | {d['passband_min_db']} / {d['passband_max_db']} | {d['stopband_worst_db']} | {d['fixed_point_samples_checked']} samples, {d['max_integer_model_error_lsb']} LSB max |")
    md+=['','## Conditions','','- Motion bank: 30 Hz motion trajectory sample rate; 17-tap 2.5 Hz nominal design cutoff.',
          '- Audio bank: 16 kHz 24-bit PCM samples; 17-tap nominal 3.2 kHz cutoff.',
          '- Values are computed from integer Q1.15 coefficient arrays, not from an ideal analogue filter.',
          '- DC/impulse/positive-negative step/edge/random sequences check integer convolution and reset at case boundaries.',
          '- Streaming UART packet CRC, coefficient-bank switch, reset cancellation and physical board operation require separate XSim and board tests.',
          '- Passband/stopband frequency regions are analysis regions, **not validated product specifications**.',
          '- Record real footage jitter, image cropping, audio noise measures and intelligibility independently.',
          '','## Sine response cross-check (model)', '']
    for name,d in data['filters'].items():
        for pr in d['sine_probes']:
            md.append(f"- {name}: {pr['frequency_hz']} Hz, integer-FIR RMS gain {pr['fixed_point_rms_gain_db']} dB vs coefficient response {pr['theoretical_gain_db']} dB")
    md+=['',f"**Model invariant gates:** {data['gates']}",'']
    (out/'filter_assessment.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print('FILTER_MODEL_ASSESSMENT',data['status'],'-',out)
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default=ROOT/'verification'/'model'/'generated',type=Path);p.add_argument('--no-plots',action='store_true')
    args=p.parse_args();assessment=run(args.output,plot=not args.no_plots)
    if assessment['status']!='PASS MODEL INVARIANTS':sys.exit(1)

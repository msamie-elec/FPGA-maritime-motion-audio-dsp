"""Write honest, reusable evidence charts and summary for a GUI run."""
from __future__ import annotations
import csv, json
from pathlib import Path
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from stabilize_video import inputs_from_csv


def export_result_files(trajectory_csv: Path, filtered: dict, metrics: dict,
                        output_dir: Path) -> dict:
    output_dir.mkdir(parents=True,exist_ok=True)
    x,y=inputs_from_csv(trajectory_csv)
    if len(x)!=len(filtered['x']) or len(y)!=len(filtered['y']):
        raise AssertionError('Export: hardware/software trajectory length mismatch')
    # Data CSV is auditable independently of video rendering.
    csvpath=output_dir/'motion_comparison.csv'
    with csvpath.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['frame','original_x_px','filtered_x_px','original_y_px','filtered_y_px'])
        for n,(xx,fx,yy,fy) in enumerate(zip(x,filtered['x'],y,filtered['y'])):
            writer.writerow([n,xx/256,fx/256,yy/256,fy/256])
    time=np.arange(len(x))/30
    source_mode=metrics['mode']
    fig=Figure(figsize=(11,6),dpi=120)
    FigureCanvasAgg(fig)
    a=fig.add_subplot(211)
    a.plot(time,np.asarray(x)/256,label='Original X')
    a.plot(time,np.asarray(filtered['x'])/256,label='Filtered X')
    a.set(ylabel='Horizontal displacement (px)',title=source_mode)
    a.grid(alpha=.2);a.legend(loc='best')
    b=fig.add_subplot(212)
    b.plot(time,np.asarray(y)/256,label='Original Y')
    b.plot(time,np.asarray(filtered['y'])/256,label='Filtered Y')
    b.set(xlabel='Time (s)',ylabel='Vertical displacement (px)')
    b.grid(alpha=.2);b.legend(loc='best')
    fig.tight_layout()
    plotpath=output_dir/'motion_curves.png'
    fig.savefig(plotpath,dpi=120)
    fig=Figure(figsize=(11,5),dpi=120)
    FigureCanvasAgg(fig)
    ax=fig.add_subplot(111)
    for raw,filt,axis in [(x,filtered['x'],'X'),(y,filtered['y'],'Y')]:
        arr=np.asarray(raw,dtype=float)/256
        out=np.asarray(filt,dtype=float)/256
        freq=np.fft.rfftfreq(len(arr),1/30)
        power=lambda a:20*np.log10(np.maximum(1e-9,np.abs(np.fft.rfft(a-np.mean(a)))/len(a)))
        ax.plot(freq,power(arr),label=f'{axis} before')
        ax.plot(freq,power(out),label=f'{axis} after')
    ax.set(xlabel='Motion frequency (Hz)',ylabel='Relative amplitude (dB)',title=source_mode+' — camera-motion spectrum')
    ax.grid(alpha=.2);ax.legend(loc='best');fig.tight_layout()
    specpath=output_dir/'motion_spectrum.png'
    fig.savefig(specpath,dpi=120)
    image_metric=metrics.get('image_stability',{})
    fig=Figure(figsize=(10,4.5),dpi=120)
    FigureCanvasAgg(fig)
    aa=fig.add_subplot(111)
    if image_metric.get('status')=='MEASURED':
        vals=[image_metric['before']['rms_high_frequency_registration_px'],
              image_metric['after']['rms_high_frequency_registration_px']]
        aa.bar(['Original frames','Stabilised frames'], vals)
        aa.set(ylabel='Independent high-frequency registration RMS (px)',
               title='IMAGE-BASED camera jitter, measured from video pixels')
        aa.grid(axis='y',alpha=.20)
    else:
        aa.text(.5,.5,'INCONCLUSIVE — not enough reliable background image motion',
                ha='center',va='center',transform=aa.transAxes)
        aa.set_axis_off()
    fig.tight_layout()
    imageplot=output_dir/'image_stability_check.png'
    fig.savefig(imageplot,dpi=120)

    report=output_dir/'RUN_REPORT.md'
    txt=f'''# Maritime camera-motion FIR — processing results

**Data provenance:** {source_mode}

**Hardware-backed, bit-exact against Python:** {'YES' if metrics.get('hardware_verified') else 'NO — SOFTWARE REFERENCE ONLY'}

**Selected COM port:** {metrics.get('physical_port') or 'None (software only)'}

**Video:** {metrics['source_video']} · {metrics['frames']} frames · ~30 fps

**X-axis high-frequency motion reduction:** {metrics['x']['reduction_pct']:.3f}%

**Y-axis high-frequency motion reduction:** {metrics['y']['reduction_pct']:.3f}%

**Target ≥30% in both axes:** {'PASS' if metrics['pass_target_30pct'] else 'NOT MET'}

**Independent image-based stability:** {metrics.get('image_stability', {}).get('status', 'NOT ASSESSED')}

**Independent measured jitter reduction (if valid):** {metrics.get('image_stability', {}).get('reduction_pct', 'N/A')}%

**Input provenance / mode:** {metrics.get('input_type', 'UNSPECIFIED')}

**End-to-end wall-clock duration (includes video, host processing & UART):** {metrics['end_to_end_wall_s']:.3f} s

**Motion estimation:** `{metrics['estimation'].get('method', 'unspecified')}`

## Interpretation and limitations

- X/Y percentages measure the high-frequency *estimated trajectory* RMS; this is not independently verified video stability. The metric is high-frequency trajectory RMS relative to a 31-frame moving average; it is **not** a measured subjective image-quality or target-tracking score.
- The independent image-content check uses background-masked phase correlation and may report INCONCLUSIVE on low-texture water scenes; do not claim an image-quality improvement from trajectory RMS alone.
- OpenCV on the laptop extracts camera motion; the FPGA filters 1-D X/Y numeric trajectories only.
- This baseline corrects *translation*, not camera roll, pitch perspective distortion, rolling shutter or independently moving vessels.
- Buffered USB-UART jobs are **not** continuous real-time video processing on the FPGA.
- FPGA mode requires successful CRC/length checks and bit-exact results versus independent Python numerical reference; software preview is explicitly distinguished.

## Saved evidence

- `motion_comparison.csv`: original vs filtered numerical trajectories
- `motion_curves.png`: before/after trajectory plots
- `motion_spectrum.png`: before/after trajectory frequency spectra
- `image_stability_check.png`: independent image-content check, or explicit inconclusive status
- `metrics.json`: machine-readable metrics and provenance
- `filtered_trajectory.json`: filtered Q16.8 samples
- `fpga_before_after.mp4` / `software_preview_before_after.mp4`: side-by-side video
'''
    report.write_text(txt,encoding='utf-8')
    return {'comparison_csv':csvpath,'curves_png':plotpath,
            'spectrum_png':specpath,'image_stability_png':imageplot,'run_report':report}

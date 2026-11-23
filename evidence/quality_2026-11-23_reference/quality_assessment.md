# Maritime audiovisual performance assessment

**Run:** `verification/system/generated/quick_test_software`
**Provenance:** SOFTWARE REFERENCE ONLY; do not claim this run used FPGA

## Video: motion and independent image stability

| Measure | Result |
|---|---:|
| Frames | 90 |
| High-frequency X trajectory reduction | 8.138% |
| High-frequency Y trajectory reduction | 5.995% |
| High-frequency THETA trajectory reduction | 5.017% |
| Independent image stability | INCONCLUSIVE |
| Crop retained area | 92.46% |

**Interpretation:** independent image-movement reduction NOT ESTABLISHED. insufficient natural background texture for independent image-based measurement

## Audio: stage-resolved measured band power

| Stage | 5–7.5 kHz change | 40–180 Hz change | 250–3000 Hz change |
|---|---:|---:|---:|
| fpga_compatible_fir | -54.94 dB | 0.0 dB | -0.09 dB |
| final_hybrid | -57.6 dB | -6.66 dB | -3.07 dB |

**Audio interpretation:** Band energy change does not establish intelligibility, isolated SNR or perceived quality.

## Qualifications

- No clean ground-truth reference audio; no measured speech intelligibility/SNR.
- Audio bands mix wanted speech and unwanted noise.
- Trajectory smoothing is not a substitute for independent image-content stability.
- Image registration can be INCONCLUSIVE for low-texture or moving-scene footage.
- Host performs frame warping, final encoding and adaptive audio stage.

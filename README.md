# FPGA Maritime Motion & Audio DSP — Project 2

**Status: Planning / engineering baseline. No FPGA hardware result has yet been claimed.**

A phased **Artix-7 FPGA + Python** signal-processing demonstrator: first smooth shipboard **camera-motion trajectories** in a fixed-point FIR core and display side-by-side original/stabilised video; then reuse the filter engine for **audio interference attenuation** and an integrated A/V demo.

> **Important scope:** The laptop decodes/warps video and estimates camera movement. The **physical FPGA processes motion trajectory samples**, not full images. All v1.0 tests are buffered/offline; later audio is also buffered. A successful demonstration will report measured results rather than infer them from simulated figures.

## Start here

- [**Master project plan: goals, full architecture, flowcharts, module hierarchy, verification, progress tracker**](docs/PROJECT2_MASTER_PLAN.md)
- [Camera-motion illustration — synthetic software data, not hardware evidence](docs/figures/motion_trajectory_concept.svg)
- [Audio DSP illustration — future extension, not hardware evidence](docs/figures/audio_spectrum_concept.svg)

## Planned releases

| Version | Purpose | Status |
|---|---|---|
| `v1.0` | FPGA FIR motion smoothing + synthetic maritime video before/after + physical verification | PLANNED |
| `v1.1` | FPGA audio noise-reduction filter with waveform/spectra and playback | BACKLOG |
| `v1.2` | Integrated synchronized audio/video before-and-after demo | BACKLOG |
| `v2.x` | More advanced FIR structures, coefficient reconfiguration, image-processing extensions | OPTIONAL |

## Hardware / software

One Digilent Arty A7-35T (`xc7a35ticsg324-1L`), USB-UART, Vivado 2025.2.1, SystemVerilog, Python/NumPy/OpenCV. No additional boards, ADC, DAC or camera interface are needed for the v1.0 demonstration.

## Related project

[Project 1 — FPGA Low-Latency Ethernet](https://github.com/msamie-elec/FPGA-low-latency-ethernet) is complete and supplies a reference for RTL/UART methodology, self-checking tests, Vivado Tcl builds, physical measurements and GitHub release discipline.

## Reproducing results

*To be added only after working source, testbench, build scripts, hardware capture and validated evidence are committed.*

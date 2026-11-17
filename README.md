# FPGA Maritime Video Stabilisation & Audio Noise Reduction

**Status:** FIR core **RTL simulation verified (M1)** · **Vivado and physical Arty A7 implementation pending**

A self-contained **AMD/Xilinx Artix-7 DSP engineering demonstrator** for smoothing shipborne camera-motion trajectories using a fixed-point **FIR filter implemented in FPGA hardware**, followed by a planned audio noise-reduction extension.

![Maritime camera looking toward a vessel at sea — illustrative concept art](docs/figures/maritime_camera_scene.svg)

*Original illustration of the intended maritime observation context — not real captured footage or an FPGA result.*

## What the demonstrator will show

![Conceptual original and corrected maritime camera view](docs/figures/maritime_before_after_concept.svg)

*Concept only. Once tested, this illustration will be accompanied by actual before-and-after frames computed from the **same** input video and **FPGA-returned** motion trajectories.*

1. A laptop loads or synthesises a short shaky ship-observation video and extracts camera-motion coordinates.
2. The laptop uploads **motion samples, not image frames**, to a Digilent Arty A7 over USB-UART.
3. The FPGA smooths the trajectory in a fixed-point FIR engine and returns numerical results.
4. Python/OpenCV applies geometric correction to the original frames and displays original vs stabilised video side by side.
5. Self-checking RTL, fixed-point reference modelling and Vivado resource/timing reports validate the engineering claims.

This is a **buffered offline demonstrator**, **not** real-time camera-frame processing, target tracking, or an RF/video interface on the FPGA. The independently moving target vessel may not stay fixed in the view.

## Engineering plan and figures

- [**Master engineering plan:** aims, objectives, full HDL hierarchy, architecture, control flow, methodology, test steps, verification gates and progress tracker](docs/MASTER_PLAN.md)
- [Synthetic camera-motion trajectory plot — not hardware evidence](docs/figures/motion_trajectory_concept.svg)
- [Illustrative audio noise-filtering spectrum — future release, not hardware evidence](docs/figures/audio_spectrum_concept.svg)

## Scope and planned releases

| Release | Capability | Current status |
|---|---|---|
| **v1.0** | Fixed-point FPGA camera-motion FIR; side-by-side ship video; bit-exact hardware proof | **PLANNED** |
| **v1.1** | FIR-based audio interference attenuation with audible A/B comparison | BACKLOG |
| **v1.2** | Synchronized before-and-after video and audio presentation | BACKLOG |
| **v2.x** | Architectural optimisation and additional signal-processing features | OPTIONAL |

## Hardware and tools

- **FPGA:** 1 × Digilent Arty A7-35T, part `xc7a35ticsg324-1L`
- **Connection:** onboard USB-UART and JTAG through the existing USB cable
- **RTL/build:** SystemVerilog, Vivado (target version 2025.2.1), 100 MHz
- **Host:** Python, NumPy, OpenCV, Matplotlib
- **v1.0 filter target:** 17-tap fixed-point symmetric motion FIR; sequential multiply-accumulate

All source code, build scripts, protocol descriptions, hardware measurements and test evidence will be maintained **within this repository**. A different project is not required to reproduce it.

## M1 development package — FIR core

The first SystemVerilog FIR module, generated Q1.15 coefficients, deterministic tests and independent Python fixed-point reference are available:

- [FIR architecture, numeric format, test instructions and caveats](docs/FIR_M1_IMPLEMENTATION.md)
- [FPGA FIR core](rtl/fir_sequential.sv)
- [Frozen coefficients](rtl/fir_coefficients.txt)
- [Self-checking SystemVerilog testbench](tb/tb_fir_sequential.sv)
- [Reference-only verification summary](evidence/m1_python_reference_summary.json)

**Verified:** 11/11 Python reference tests PASS and **9/9 RTL regression cases PASS (1,377 checked samples, including reset)** in both Icarus [GitHub Actions](https://github.com/msamie-elec/FPGA-maritime-motion-audio-dsp/actions/runs/44105628765) and local Windows Vivado 2025.2.1 XSim (console screenshot supplied 17 November 2026). **Pending:** FIR-only Vivado synthesis/resource assessment, routed timing and physical FPGA testing.

From the repository root, with Python and pytest installed:

```bash
python host/generate_vectors.py
python -m pytest -q tests/test_fixed_point.py
```

On Windows with Vivado simulator tools available in PATH, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_fir_xsim.ps1
```

The script generates coefficients/vectors, runs Python tests and **then runs the actual SystemVerilog testbench**. The output must report `FIR_RTL_REGRESSION_PASS` before the RTL gate is declared passed. An M1 source-level Vivado inspection project can be generated with `scripts/create_fir_m1_vivado.tcl`; it is not yet a board-programmable design.

## M2 synthesis investigation — next step

- [Clock-only 100 MHz synthesis procedure and report checklist](docs/FIR_M2_SYNTHESIS.md)
- [Reproducible Vivado Tcl script for FIR-only synthesis](scripts/run_fir_m2_synthesis.tcl)
- [10 ns FIR-core clock constraint](constraints/fir_m2_clock_only.xdc)

The generated `maritime_fir_m1.xpr` is a **FIR-core inspection project**, not a board top. Synthesis and its utilization/timing estimates must not be presented as place-and-route timing closure or FPGA hardware validation.

## Reproducing results

*The FIR-core simulation commands are documented above. Complete board-level build/programming and measured video-reproduction instructions will be added only after hardware implementation. No FPGA performance measurements are claimed yet.*

# Host software and FPGA quick start

The supported, current installation instructions are in [`../START_HERE_WINDOWS.txt`](../START_HERE_WINDOWS.txt).

- Host application and PC-side adaptive audio/video routines: `host/`
- Numerical reference/filter tests: `verification/model/tests/`
- End-to-end software and protocol tests: `verification/system/tests/`
- FPGA testbenches/vectors: `hardware/sim/`
- One native Vivado project and its implementation output: `hardware/build/`

The FPGA operates on buffered fixed-point motion/audio samples, not raw pixels. The host performs video warping and adaptive spectral denoising.

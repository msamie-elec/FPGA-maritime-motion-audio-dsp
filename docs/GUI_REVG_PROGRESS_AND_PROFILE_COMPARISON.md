# RevG — responsive GUI, safe cancellation and stabilisation profile comparison

**Date:** 23 November 2026. **Scope:** Python GUI, host video/audio pipelines and
verification. No synthesizable SystemVerilog, constraints, coefficients, or
Vivado project metadata were modified from the verified RevD/RevF baseline.

## What changed

- The Implementation tab has a persistent processing-state row: an approximate
  **workflow completion** indicator, current stage, stage counter and elapsed
  wall time. This is **not a forecast of time remaining or native FPGA speed**.
- The **Cancel processing** action sets a cooperative cancellation flag. The
  host checks it between *complete* FPGA UART transactions and during video
  estimation/rendering, independent image assessment, and audio processing.
  A cancelled FFmpeg operation is terminated on the host, not via FPGA reset.
  Completion of an in-flight UART transaction can delay acknowledgement.
- Incomplete runs receive `CANCELLED.json` with
  `CANCELLED_NOT_VERIFIED`. No cancelled operation is presented as FPGA PASS.
  Closing a window during an active job requests controlled cancellation
  rather than killing the process without releasing the serial interface.
- **Video Assessment → Compare Normal / Strong** creates an independent
  two-profile *software-reference* assessment for the selected video; each
  profile has its own output folder and a common JSON/Markdown comparison.
  The comparison never reads the FPGA and never overwrites a hardware run.

## Actual software-reference profile results, three-second demo

Input: `videos/03_Unified_Quick_Test_3s.mp4` (90 frames, 30 fps). Both
profiles were run on the same source using the unchanged signed 17-tap FIR
model and host-side affine warping, with a separate OpenCV motion estimate.

| Metric | Normal | Strong |
|---|---:|---:|
| X HF trajectory reduction | 8.14% | 12.97% |
| Y HF trajectory reduction | 5.99% | 9.57% |
| Roll HF trajectory reduction | 5.02% | 8.80% |
| Fixed-crop retained frame area | 92.46% | 91.23% |
| Independent image-content stability | INCONCLUSIVE | INCONCLUSIVE |

Strong uses **two passes** of the existing FPGA-compatible FIR per axis;
this is why it can smooth the trajectory more. Neither these trajectory
metrics nor a near-identical pair of screenshots establishes visibly
better stabilisation. Natural scene motion, feature loss and relative
movement of ships/waves may degrade camera-motion estimation. Use
representative real boat-mounted footage with stationary background and
an independent image/content assessment before making claims.

## Reproduce in the Windows GUI

1. Install host requirements, and launch the unchanged launcher:
   `powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1`
2. Load the three-second demonstration MP4. Choose **Software preview**
   (or **Process on FPGA** with the RevD bitstream already programmed).
3. Observe staged progress and, if needed, use **Cancel processing**. Do
   not reset BTN0 or disconnect COM4 while an active transaction finishes.
4. On Video Assessment click **Compare Normal / Strong**. This compares both
   profiles using the CPU reference. Inspect the JSON/Markdown under
   `verification/system/generated/profile_comparisons/<timestamp>/`.
5. If Strong is preferable for this source, choose **Strong** in the
   Smoothing selector for a separate actual FPGA run. This uses the same
   bitstream and bit-exact check; it simply sends the FIR output through a
   second existing pass.

## Validation boundaries

- Run suite: **98 passed** with Xvfb GUI display on Linux, including
  cancellation tests, full mathematical model and the prior GUI tests.
- A complete 3-second video+audio software GUI job reached 100% and wrote its
  output in a separate sandbox, and the async profile comparison completed.
- **New host features have not been exercised on the operator's Windows PC**.
  FPGA/UART hardware tests remain established by the owner's RevD evidence;
  no post-RevG physical run is claimed.
- Existing warm soak failure (141 COM4 access-denied jobs in one attempt)
  remains a historical failure despite a clean 4,408/4,408 retest.
- Progress is approximate *stage completion*, not a timing/temperature sample.
  XADC readings are from Vivado and must not be collected concurrently with
  a UART job in the present operator setup without separate validation.

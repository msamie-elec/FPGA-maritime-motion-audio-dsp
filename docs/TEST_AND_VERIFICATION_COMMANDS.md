# Testing and verification commands — Maritime FPGA DSP

**Applies to:** portable project folder containing `hardware/`, `host/`, `verification/` and `scripts/`. **Platform:** Windows PowerShell; Vivado 2025.2.1 for HDL and FPGA build. **Hardware:** Arty A7-35T. **Evidence types:** software model, RTL/XSim, post-route static estimate, physical FPGA UART, host audiovisual, and JTAG XADC are distinct.

Start PowerShell **in the extracted project root**. Never run the GUI and a separate UART verification script on the same COM port at the same time. Replace `COM4` if Windows assigned a different port. The scripts do **not** program the board. An earlier verified RevD `.bit` remains compatible with host-only updates because the RTL/XDC are unchanged.

## 1. Prepare and launch the GUI

**Purpose / GUI result:** `Implementation` loads the source; the other tabs show results after processing. Install requirements once, then launch.

```powershell
python -m pip install -r .\host\requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

In the GUI select the supplied `videos\03_Unified_Quick_Test_3s.mp4`, choose `Video + Audio`, `Normal` or `Strong`, and choose `Software preview` (PC only) or `Verify FPGA` then `Process on FPGA` (board required). `Play` is finished-file playback, **not an FPGA workload**.

## 2. Software mathematical filter tests (no FPGA)

**Purpose / GUI result:** `Summary Report → FIR design curves` shows model-only impulse/DC, fixed-point edge cases and frequency-response plots. Does not prove bitstream correctness.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_engineering_assessment.ps1
```

Outputs: `verification\model\generated\filter_assessment.json`, `filter_assessment.md` and frequency-response graphics. The run also invokes relevant reference-model tests and summary export.

## 3. Host software, GUI and end-to-end regression (no FPGA)

**Purpose / GUI result:** Tests `Implementation` playback/cancel, system pipeline, `Video Assessment`, `Audio Assessment`, and summary calculations. Tests do not establish a hardware pass. Some GUI tests require a desktop session.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
python -m pytest -q verification\model\tests verification\system\tests
```

Keep failing test output. Some GUI tests display windows and may require manual interaction on the operator PC. Do not infer successful hardware testing from passing pytest.

## 4. HDL simulation with testbenches (Vivado XSim)

**Purpose / evidence:** `hardware\sim\tb\` verifies the FIR RTL, UART receive/transmit path, coefficient-bank switching and reset. Reports are **simulation**, not measured on the board. Run in a Vivado-enabled PowerShell where `xvlog`, `xelab` and `xsim` are on PATH.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\hardware\sim\scripts\run_fir_xsim.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\hardware\sim\scripts\run_maritime_xsim.ps1
```

A native project for inspecting sources and running simulations is at `hardware\build\maritime_a7.xpr`. If XSim reports a failure, retain its transcript; do not proceed to release hardware claims.

## 5. Synthesis, implementation, timing, DRC and power (Vivado)

**Purpose / GUI result:** `Summary Report` shows current generated report evidence or a clearly labelled archived baseline. Rebuild **only when RTL/XDC/part/implementation settings change**, or you deliberately want a fresh implementation. A new host-only release does not require this step.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\final_rebuild_and_reports.ps1
```

The build writes its `.bit` into `hardware\build\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit`, generates `hardware\build\reports\`, and archives evidence in `evidence\final_validation\build_<timestamp>\`. Inspect routed setup/hold slack, DRC, methodology, utilisation and power assumptions. `0.071 W` was a **vectorless Vivado estimate**, not measured board power.

If you implemented using the **Vivado GUI**, open the routed design and run from the project's Tcl Console:

```tcl
cd {C:/path/to/extracted/project}
source hardware/vivado/export_open_vivado_reports.tcl
```

Then select `Summary Report → Refresh evidence`. This export does not rerun implementation.

## 6. Program the existing verified bitstream (board prerequisite)

**Purpose:** physical tests require a matching verified dual-bank `.bit` already programmed through Vivado Hardware Manager. The cleaned source ZIP intentionally omits generated bitstreams. You can use your previously verified `FPGA_Maritime_AV_7` RevD `.bit` when only host code changes.

```text
Vivado → Open Hardware Manager → Open Target → Auto Connect → Program Device
Choose the previously verified bit file:
FPGA_Maritime_AV_7\hardware\build\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit
```

Confirm the board is configured, the correct UART COM port is assigned, and **no other process owns COM4**. Do not treat finding a `.bit` path as proof that it was loaded; preserve the bitfile hash/operator record.

## 7. Physical dual-bank FIR verification and 3-second combined MP4

**Purpose / GUI result:** `Implementation → Verify FPGA / Process on FPGA` and `Video Assessment`/`Audio Assessment`. Run this command with the GUI closed to prevent COM4 conflicts.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_unified_av_hardware.ps1 -Port COM4
```

This checks numeric motion/audio FIR banks and mode switching against the independent Python golden model, then produces a 3-second physical-FPGA-processing demonstration. Outputs: `evidence\hardware\unified_av_<timestamp>\` and `videos\hrd\unified_av_<timestamp>\`. The FPGA computes numeric FIR jobs; the PC estimates/wraps image frames and performs optional adaptive spectral cleanup.

## 8. Physical reset reliability (10 button cycles)

**Purpose / GUI result:** `Summary Report → Reliability` after evidence import. Perform physical BTN0 press/release **at each script prompt**. It is not a true power-cycle. Close any GUI/serial terminal using COM4.

```powershell
python .\verification\system\maritime_reliability.py --port COM4 --mode reset --cycles 10 --warm-runs 1 --settle-s 5
```

Outputs: `evidence\final_validation\reset_<timestamp>\results.csv` and `summary.json`. Record skipped/unperformed cycles honestly.

## 9. Physical cold-start reliability (5 cycles)

**Purpose / GUI result:** `Summary Report → Reliability`. At each prompt physically disconnect/reconnect power, **reprogram the bitstream if FPGA configuration was lost**, reconnect COM4, and only then enter `READY`. The 5-second settle is **not measured startup time**.

```powershell
python .\verification\system\maritime_reliability.py --port COM4 --mode cold --cycles 5 --warm-runs 1 --settle-s 5
```

Outputs: `evidence\final_validation\cold_<timestamp>\`. Preserve operator notes and failed cycles.

## 10. Sustained workload soak (15 minutes)

**Purpose / GUI result:** `Summary Report → Reliability`. This is ordinary-operation stability, **not** a controlled elevated-temperature test. Avoid COM4 conflicts: run with GUI and other serial tools closed.

```powershell
python .\verification\system\maritime_reliability.py --port COM4 --mode soak --minutes 15
```

Outputs: `evidence\final_validation\soak_<timestamp>\results.csv`, `summary.json`. Preserve **both** the original 4,523 PASS / 141 COM4-access failures and the clean 4,408/4,408 retest. Neither erases the other. Bit-exact UART pass rate is not speech quality or image stabilisation quality.

## 11. Normal versus Strong camera stabilisation

**Purpose / GUI result:** `Video Assessment → Compare Normal / Strong → Profile comparison` produces a **software-reference** four-row table (X/Y/roll high-frequency trajectory reduction and frame area retained), independent image registration, source SHA-256 and provenance. It does not send jobs to the FPGA.

```text
GUI → Implementation → Open video → select a source
GUI → Video Assessment → Compare Normal / Strong
GUI → Video Assessment → Profile comparison
```

Outputs: `verification\system\generated\profile_comparisons\<timestamp>\profile_comparison.json` and `.md`. The archived three-second clip reference is `evidence\quality_2026-11-23_reference\normal_strong_reference.json`. Choose Strong for a **separate** real FPGA run only if its added crop and image appearance are acceptable.

## 12. Quantitative video/audio quality after a completed run

**Purpose / GUI result:** `Video Assessment` / `Audio Assessment` / `Summary Report → Quality charts`. Select the **actual generated run folder** (`videos\hrd` for physical FPGA, `videos\sim` for software). Replace `<run_folder>` with the real name.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_media_quality.ps1 -RunDir ".\videos\hrd\<run_folder>"
```

This assesses available motion curves, image registration, crop, and audio spectral bands. An `INCONCLUSIVE` image result is not a visual pass. Band attenuation does **not** prove improved speech intelligibility or removal of isolated wind/sea noise.

## 13. XADC die-temperature snapshots — Vivado Tcl Console only

**Purpose / GUI result:** `Summary Report → Die temp (XADC)`. Read the Artix-7's built-in die-temperature sensor through JTAG, **not through the UART FIR RTL**. On this operator workstation, do **not** sample while an active GUI UART job is running; the concurrent workflow has not been validated. Read idle or promptly after the GUI job finishes.

```tcl
cd {C:/path/to/extracted/project}
set ::env(MARITIME_PHASE) idle
source hardware/vivado/sample_xadc_snapshot.tcl
# Immediately AFTER a completed workload:
set ::env(MARITIME_PHASE) post_processing
source hardware/vivado/sample_xadc_snapshot.tcl
```

Outputs: `evidence\final_validation\xadc_snapshots.csv`. Each reading is an instantaneous die temperature; no earlier peak can be reconstructed. Record ambient temperature and actual workload timing separately. The 36 operator XADC snapshots from 23 November ranged from 31.6–32.4°C (latest 32.2°C); these are idle and post-processing snapshots, not a continuously recorded under-load trace. Historical soak_end labels were not all verified soak workloads.

## 14. Import verified evidence, refresh summary and stage GitHub

**Purpose / GUI result:** `Summary Report → Refresh evidence` and `Export report`. Import raw CSV/JSON from the previously tested project instead of treating screenshot-derived totals as complete machine evidence. Substitute the real folder path.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\import_local_validation_evidence.ps1 -PreviousProjectRoot "C:\path\to\FPGA_Maritime_AV_7"
```

The GitHub script **stages** a cleaned source checkout by default. Inspect the staged diff before pushing; do not push proprietary or unlicensed videos, generated `.bit`/runs, or local serial logs.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare_github_release.ps1
# Only AFTER reviewing staged changes and correct branch:
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare_github_release.ps1 -Push
```

The staging branch is not the main branch. Do not claim a release has been published until its GitHub contents and CI are verified.

---

**Interpretation key:** **MODEL PASS** is software mathematics; **XSIM PASS** is RTL simulation; **ROUTED PASS** means relevant constrained timing gates met; **PHYSICAL BIT-EXACT PASS** is board-returned integer equality; **QUALITY MEASURED** describes specifically observed audio/video effects; **XADC MEASURED** is sampled die temperature. These labels are not interchangeable.

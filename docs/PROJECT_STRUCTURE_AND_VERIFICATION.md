# Maritime FPGA AV — canonical source tree and verification levels

The purpose of **RevD** was packaging and portability; the **23-Nov evidence update** adds quality tooling and routed/physical owner evidence, without RTL/XDC changes. It does **not** modify
RevC filter arithmetic, reset synchroniser or pin-level logic. The original
`rtl/`, `tb/`, `constraints/`, and duplicated `vivado_maritime_a7` project
are no longer used. Source paths are relative to the package root.

```text
FPGA_Maritime_AV_Engineering_Release_RevD/
├── README.md, START_HERE_WINDOWS.txt, OPEN_VIVADO_PROJECT_WINDOWS.ps1
├── hardware/
│   ├── rtl/                 Synthesizable RTL and coefficient-bank ROMs
│   ├── constraints/         Arty A7 XDC
│   ├── build/               ONE maritime_a7.xpr (tracked)
│   │                        Routed runs, reports, bitstream (generated/ignored)
│   ├── vivado/              Project-generation, build, report and XADC Tcl
│   └── sim/
│       ├── tb/              Self-checking SystemVerilog testbenches
│       ├── vectors/         Hex vectors + bit-exact golden output files
│       ├── scripts/         XSim / Icarus command-line simulation runners
│       └── checks/          Non-HDL structural regression tests
├── host/                    Python GUI, models, UART, video/audio pipeline
├── verification/
│   ├── model/               Filter characteristic calculator + Python tests
│   │   ├── tests/           Impulse/DC/random/sign/quantisation tests
│   │   └── generated/       CSV, response plots, model assessment
│   └── system/              Full GUI/protocol/media/system validation
│       ├── tests/           Integration and system-level regressions
│       ├── maritime_reliability.py  Physical cold/reset/soak runner
│       └── generated/       Current evidence-driven GUI summary
├── scripts/                 Top-level orchestration and GUI/demo entrypoints
├── evidence/                Historical or new post-route and physical evidence
├── docs/                    Design notes, evidence limitations, screenshots
└── videos/                  Local licensed/permission-dependent input clips
```

## Verification level 1 — numerical / reference model (CPU only)

**Location:** `verification/model/tests/`,
`verification/model/industrial_filter_assessment.py`, model outputs
`verification/model/generated/`.

**Purpose:** ideal and quantised FIR response, DC/impulse characteristics,
negative fixed-point rounding, saturation and random/full-scale sample checks.
No Vivado, RTL execution, UART or board needed.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_engineering_assessment.ps1
```

## Verification level 2 — RTL / digital hardware simulation

**Location:** `hardware/sim/tb/`, `hardware/sim/vectors/`,
`hardware/sim/scripts/`, `hardware/sim/checks/`.

**Purpose:** HDL vs bit-exact software vectors for BOTH coefficient banks,
FIR state/edge cases, bank switching, UART CRC/framing, BTN0 reset and recovery.
Self-checking SystemVerilog testbenches support Vivado XSim on Windows; Icarus
is an optional portable simulator in CI.

```powershell
powershell -ExecutionPolicy Bypass -File .\hardware\sim\scripts\run_fir_xsim.ps1
powershell -ExecutionPolicy Bypass -File .\hardware\sim\scripts\run_maritime_xsim.ps1
```

## Verification level 3 — integrated end-to-end behaviour and physical board

**Location:** `verification/system/tests/`, `host/` pipeline and GUI,
`verification/system/maritime_reliability.py`; physical observations saved
under `evidence/final_validation/` or `evidence/hardware/`.

**Purpose:** source video/audio -> host preprocessing -> UART -> FIR sample
outputs -> host warping and spectral audio cleanup -> saved media/quality
assessment. Separate tests assess packet loss/error recovery, cold vs reset
repeatability, warm workload, GUI playback, sample bit-exactness, and
real-clip perceptual/stability metrics.

**Boundary:** software-only integration checks are NOT physical FPGA checks.
No numerical FIR test alone proves useful image stabilisation or intelligibility.
The submitted video clips are not necessarily licensed for public GitHub use.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
# After Vivado synthesis/implementation AND manually programming the FPGA:
powershell -ExecutionPolicy Bypass -File .\scripts\verify_unified_av_hardware.ps1 -Port COM4
```

## Generated versus tracked files

The **only** Vivado `.xpr` is `hardware/build/maritime_a7.xpr`. The `-Recreate`
launcher regenerates this same file; it does not make a second project.
`hardware/build/maritime_a7.runs`, reports, and `.bit` are generated and must
not be committed as source. The release ZIP includes the authoritative `.xpr`
and the archived, separately labelled measured/estimated evidence, but no
locally-generated bitstream. The full build script preserves historical
renderings separately and refuses release when REQP-1840/CFGBVS-1 return.

## Provenance of baseline results

Uploaded **RevC** routed reports (21 November 2026, 12:00) show 100 MHz,
+1.740 ns WNS, +0.046 ns WHS, 632 LUTs, 857 registers, one DSP48E1 and two
RAMB18, 0.071 W **vectorless estimate**. They contain three advisory DRC
instances (DPIP-1 twice, DPOP-1 once), no REQP-1840/CFGBVS-1.
These reports predate RevD path relocation and do not independently verify
that a RevD bitstream was built or programmed. Current-route validity
requires a fresh Windows Vivado XSim/synthesis/implementation run.

## 23 November 2026 evidence and media assessment update

Owner's RevD physical test and routed implementation have now been captured in
`evidence/owner_2026-11-23_revd/`; see
`docs/ENGINEERING_RELEASE_2026-11-23.md`. Original passing raw CSV/JSON remain
on the owner's prior project and must be imported for full reproducibility.
The earlier failed soak is retained.

Software-reference media assessment is in
`evidence/quality_2026-11-23_reference/`; run
`verification/system/media_quality_assessment.py` to assess new completed
processing directories. These are level-3 *system* quality proxies, distinct
from mathematical FIR correctness (level 1) and XSim RTL verification (level 2).
No 23-Nov host-only evidence edit changes the validated hardware design.

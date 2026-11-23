# Maritime FPGA audiovisual DSP — engineering evidence review

**Evidence cutoff:** 23 November 2026. **Target:** Digilent Arty A7-35T,
Artix-7 `xc7a35ticsg324-1L`, Vivado 2025.2.1, 100 MHz.
**Source:** unchanged RevC/RevD RTL; this evidence/documentation update does not
require a new synthesis, place-and-route or FPGA reprogramming.

## Executive summary

The owner's **RevD** implementation on 23 November met internally constrained
100 MHz setup/hold timing with +1.740 ns WNS, +0.046 ns WHS, and zero negative
total slack; 632 LUTs, 857 registers, one DSP48E1, two RAMB18 and eight I/O
were reported. Post-route vectorless estimated on-chip power is 0.071 W,
**not** measured board consumption. Source: uploaded Vivado `.rpt` files
preserved under `evidence/owner_2026-11-23_revd/reports/`.

The owner demonstrated bit-exact FIR operation, reset recovery, five cold
power/reconfiguration cycles and a clean 15-minute continuous-operation retest.
The earlier unsuccessful soak (141 COM4 access-denied errors) remains recorded
as a **failed separate run**; the subsequent 4,408/4,408 pass does not erase it.
Original successful-run CSV/JSON files should be imported from the owner's
working directory to strengthen reproducibility.

**Release status:** an evidence-backed engineering demonstrator, not a certified
commercial video stabiliser, speech enhancement system or environmental
qualification.

## 1. Independent implementation evidence

| Post-route metric (23 Nov RevD) | Result | Scope |
|---|---:|---|
| 100 MHz clock | 10.000 ns period | Single constrained design clock |
| WNS / TNS | +1.740 / 0.000 ns | Internal setup timing |
| WHS / THS | +0.046 / 0.000 ns | Internal hold timing |
| LUTs | 632 | Routed resource report |
| Registers | 857 | Routed resource report |
| DSP48E1 | 1 | Routed resource report |
| RAMB18 | 2 | Routed resource report |
| Bonded I/O | 8 | Routed resource report |
| Power | 0.071 W | Vivado **vectorless estimate**, not measurement |

**DRC and timing qualification:** former `REQP-1840` and `CFGBVS-1` are absent
from the 23 November DRC reports. The three remaining warnings are `DPIP-1` ×2
and `DPOP-1` ×1 (DSP pipeline optimisations). `SYNTH-6` advises on BRAM output
register timing. Seven external I/O delay checks remain scoped by asynchronous
interface exceptions, and should be justified as part of interface sign-off.
No full external timing or physical power sign-off is claimed. Vivado also
warns about vectorless high-fanout reset switching assumptions (`Power 33-332`).

## 2. Actual FPGA test history (owner-supplied)

| Test | Date | Results | Primary evidence | Boundary |
|---|---|---|---|---|
| Dual-bank physical FIR / combined 3 s MP4 | 23 Nov | 4 motion/audio/switch jobs bit-exact; 48,000 audio samples processed in 97 FPGA jobs | Owner PowerShell screenshot | Bitstream SHA not independently read from FPGA |
| BTN0 reset | 23 Nov | 80/80 jobs, 10 reset cycles | Owner PowerShell screenshot | Manual button/release prompts |
| Cold power/reconfiguration | 23 Nov | 40/40 jobs, 5 operator actions | Owner PowerShell screenshot | Five-second test dwell is not measured start latency |
| First continuous-operation soak | 23 Nov | **4,523 pass, 141 FAIL / 4,664** | Uploaded `results.csv` and `summary.json` | Windows `COM4` access denied in brief bursts, no reported arithmetic mismatch in completed jobs |
| Repeat continuous-operation soak | 23 Nov | **4,408/4,408 pass, 0 fail**, 1,102 × four-job cycles | Owner PowerShell screenshot | Approx. 15 min normal workload, **not** thermal chamber qualification |

The failed first soak was analysed using the original uploaded CSV. All 141
errors occurred when opening `COM4`, consistent with a temporary host serial
ownership or driver conflict. **The responsible process was not identified.**
No successful job had a reported bit-exact mismatch. The clean later soak
supports recovery under those conditions, but is not proof the host-port problem
can never recur.

Original CSV/JSON for the successful retest, reset and cold runs were not
attached. On the owner's PC, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\import_local_validation_evidence.ps1 -PreviousProjectRoot 'C:\...\FPGA_Maritime_AV_7'
```

The script copies logs without overwriting earlier failure evidence. The GUI
Summary Report will prioritise those original logs if present.

## 3. Three verification tiers

| Tier | Evidence and tooling | Meaning |
|---|---|---|
| Software mathematical FIR | `verification/model` (impulse/DC/frequency response/extremes) | Quantisation and coefficient design |
| Self-checking RTL tests | `hardware/sim` (FIR core, packet/CRC, reset) | HDL behaviour in XSim/Icarus, not physical timing |
| Integrated and physical AV | `verification/system` + COM4 + video/audio | Numerical hardware proof, reliability and audiovisual proxy measurements |

The FPGA performs only buffered motion/audio sample FIR filtering. Motion
estimation, perspective warp, adaptive audio noise reduction and MP4 encoding
execute on the PC. The physical test proves that the FPGA computed sample
values correctly under the tested protocol. It does **not** automatically prove
that arbitrary ship footage becomes visually stable or that speech is clearer.

## 4. Media quality assessment

The supplied three-second `videos/03_Unified_Quick_Test_3s.mp4` was processed
**locally as SOFTWARE REFERENCE ONLY** using the exact same fixed-point FIR
model and host video/audio processing. Its results are recorded in
[`MEDIA_QUALITY_2026-11-23.md`](MEDIA_QUALITY_2026-11-23.md). The model and
physical FIR are separately bit-exact in the owner's test, but this local MP4
was *not* sent to an attached physical FPGA.

## 5. Open review items

- Preserve source hashes and exact local bitstream SHA (from original Vivado
  build manifest) and board programming evidence; logs currently carry
  `UNCONFIRMED_ON_DEVICE`.
- Import actual original passing cold/reset/clean-soak `results.csv` and
  `summary.json`; screenshots alone are incomplete machine-readable evidence.
- 36 XADC die-temperature snapshots have now been supplied (31.6–32.4°C),
  including 20 post-processing readings. These are *snapshots*, not a continuous
  under-load trace or measured hot-environment qualification.
- Investigate or document the host COM4 port conflict and avoid concurrent
  serial applications. Improve serial exclusivity if it recurs.
- Review remaining external I/O exceptions and nonblocking DSP advisories.
- Obtain redistribution permission for video and still imagery before any
  public repository release; sample clips are excluded from GitHub staging.
- Collect motion-rich **real maritime** video with stationary textured
  background to assess independent image-based stabilisation; use listening or
  annotated clean reference data to establish perceptual speech outcomes.

## 6. Next-build decision

**No further synthesis, implementation or bitstream generation is needed for
this report/UI/test-tool change.** The same verified RTL and XDC are retained.
A new Vivado build is required only if the FPGA design, device, constraints,
coefficients or clocking change, or if an independently verifiable build
provenance is specifically required.


## RevF navigation and temperature-evidence clarification

The duplicated top-menu navigation has been removed. Advanced inputs are
accessible from **Implementation → Tools**, and the audio cleanup selector is
visible in the Implementation tab. No synthesizable RTL or constraints changed.

**XADC die temperature has been physically sampled 36 times.** The existing
Vivado script `hardware/vivado/sample_xadc_snapshot.tcl` records real snapshots;
the Summary Report uses the local CSV when present and otherwise loads the
clearly labelled archival CSV from `evidence/xadc_2026-11-23/`. If no CSV exists,
it displays **NOT MEASURED**.
Instructions: [XADC Die Temperature](XADC_DIE_TEMPERATURE.md).

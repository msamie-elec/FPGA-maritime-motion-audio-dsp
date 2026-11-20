# Unified maritime video + audio: physical FPGA validation — 20 November 2026

> **Evidence status:** User-supplied Vivado 2025.2.1 Hardware Manager screenshot, physical serial verification console screenshot, and four original post-route Vivado reports. This document records observations on the local **v1.0.3 unified development package**. The integrated v1.0.3 source itself is not yet merged into GitHub `main`; do not mistake this verification record for a complete release.

## Validated hardware

- Board: Digilent Arty A7-35T, Artix-7 device `xc7a35ticsg324-1L`.
- Programming: Hardware Manager shows device programmed successfully, startup status HIGH and no embedded debug cores (expected).
- Physical serial port: COM4.
- FIR architecture: shared single DSP48E1 implementation with distinct motion (30 Hz trajectory) and audio (16 kHz PCM) coefficient banks.

## Physical UART/FIR tests: PASS

The user-reported physical script returned these bit-exact outcomes:

| Test | UART job ID | Verified output samples |
|---|---:|---:|
| Motion impulse | 0x11 | 48 |
| Audio impulse | 0x81 | 48 |
| Audio mixed-sign | 0x82 | 40 |
| Motion after audio-bank switch | 0x12 | 48 |

Console marker: `DUAL_BANK_PHYSICAL_FPGA_PASS`. This verifies switching between the coefficient banks and returning to the original bank, with exact matching against the Python reference for those tests.

## Unified three-second processing: PASS (functional)

The console reports `UNIFIED_AV_PHYSICAL_FPGA_PASS` and `hardware_verified=true`, with both motion/video and audio marked as physically bit-exact. It generated `final_stabilised_filtered_audio.mp4` under a timestamped `videos/hrd/unified_av_*/` directory and a corresponding `combined_metrics.json`.

Audio details: 16,000 samples/s mono, **48,000 processed samples**, **97 UART audio jobs**; source audio decoded to 47,659 samples and **341 samples of trailing silence** were added to align the clip duration to 3 seconds.

The audio analysis reports **−54.96 dB** change in the 5–7.5 kHz band and **−0.09 dB** change in the 250–3000 Hz band. Those figures show spectral suppression, **not** measured speech intelligibility or removal of in-band engine/wind noise. The screenshot alone does not permit direct inspection/listening of the resulting MP4, or independent judgement of visual stability.

## Routed implementation and timing

Source reports: `timing_routed(1).rpt`, `utilization_routed(1).rpt`, `utilization_synth(1).rpt`, `drc_routed(1).rpt` supplied on 20 November.

| Item | Routed result |
|---|---:|
| Defined internal clock | 100 MHz, 10.000 ns |
| WNS / TNS | +0.916 ns / 0.000 ns |
| WHS / THS | +0.034 ns / 0.000 ns |
| Setup/hold failing internal endpoints | 0 / 0 |
| Slice LUTs | 630 / 20,800 (3.03%) |
| Slice registers | 856 / 41,600 (2.06%) |
| DSP48E1 | 1 / 90 (1.11%) |
| RAMB18E1 | 2 / 100 (2.00%) |
| Bonded IOB | 8 / 210 (3.81%) |

All user-specified *internal* timing constraints were met. This is **not** a claim of full interface timing sign-off.

## Open issues before final release

1. **DRC warnings: five instances across four rule types**: `CFGBVS-1` (missing configuration voltage settings), `DPIP-1` (two DSP input pipeline warnings), `DPOP-1` (DSP output PREG warning), `REQP-1840` (one RAMB18 asynchronous reset control warning that could affect data/read reliability).
2. **Seven external I/O delay omissions** (two input, five output) reported as `TIMING-18`. Review actual asynchronous UART/reset and other interfaces and constrain/except appropriately; do **not** invent arbitrary delays to make the warning disappear.
3. Test BRAM/reset behaviour specifically under repeated button reset, UART start/stop, and mid-job recovery.
4. Record real audiovisual quality evaluation separately from mathematical bit-exact tests (visual jitter/crop, listening quality and sound/video synchronization).
5. Confirm long 30-second hardware path with many overlapping UART batches and evaluate performance/time, since the demonstrated hardware run is a short three-second case.
6. Publish and tag the matching **v1.0.3 unified** RTL/software source and report provenance; avoid merging to `main` until source and evidence are reconciled.

## Evidence interpretation

**Physical numerical functionality: verified for the supplied short test.** **Timing: internally met, with external-constraint and DRC review still needed.** **Audiovisual quality / long-form hardware validation: pending.**

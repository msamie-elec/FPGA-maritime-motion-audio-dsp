# FIR Core — M2 Vivado Synthesis and Resource Review

**Status:** READY TO RUN LOCALLY. No synthesis, implementation, timing-closure or physical-board result is asserted in this document.

## Baseline confirmed before M2

On 17 November 2026, the user's local Windows PowerShell console showed `11 passed` in pytest, successful Vivado 2025.2.1 `xvlog` and `xelab`, all eight FIR vector cases plus the reset cancellation test, and `FIR_RTL_REGRESSION_PASS tests=9 samples=1377`. GitHub Actions also previously passed the equivalent Icarus regression. This closes the standalone FIR **RTL simulation gate**, not the FPGA physical validation gate.

## Goal of this step

Check how AMD Vivado maps the synthesizable `rtl/fir_sequential.sv` core to the **Artix-7 XC7A35T**. Record LUT, flip-flop, inferred DSP48E1, block-RAM use and preliminary timing *estimates* under a nominal **100 MHz** clock.

The FIR is currently the design top, with raw data/control ports but no UART, board pinout, reset synchronizer or board-ready implementation. It is **not** a bitstream-ready Arty top-level. Do not treat post-synthesis slack as routed timing closure.

## Reproducible command-line route (recommended)

From an up-to-date repository folder, and **with the Vivado GUI closed** (the script updates the same `.xpr`):

```powershell
& "C:\AMDDesignTools\2025.2.1\Vivado\bin\vivado.bat" -mode batch -source scripts/run_fir_m2_synthesis.tcl
```

Prerequisite: the FIR inspection project exists at `build/vivado_fir_m1/maritime_fir_m1.xpr` (created earlier with `scripts/create_fir_m1_vivado.tcl`). The script adds `constraints/fir_m2_clock_only.xdc`, refreshes synthesis, opens the synthesized netlist, and writes:

- `build/vivado_fir_m1/reports_m2/fir_utilization_post_synth.rpt`
- `build/vivado_fir_m1/reports_m2/fir_timing_post_synth.rpt`
- `build/vivado_fir_m1/reports_m2/fir_post_synth.dcp`

The required terminal message is `M2_FIR_SYNTHESIS_REPORTS_READY`. If Vivado shows an error or warning, retain the full log rather than ignoring it. **This batch script has been authored but not locally executed in Vivado by the assistant**; the first run is the validation of the script itself.

## Vivado GUI alternative

If you prefer the open GUI project:

1. Open `build/vivado_fir_m1/maritime_fir_m1.xpr`.
2. In **Sources → Constraints → Add Sources → Add or Create Constraints**, add `constraints/fir_m2_clock_only.xdc` (the clock-only constraint, not a board XDC). It contains `create_clock -name fir_clk -period 10.000 [get_ports clk]`.
3. In **Flow Navigator → Synthesis**, select **Run Synthesis**.
4. On completion, select **Open Synthesized Design**, then **Report Utilization** and **Report Timing Summary**. Save the reports.
5. In the synthesized schematic inspect whether the signed 24×16 multiply has inferred `DSP48E1` and note the actual count. Do not infer DSP count from RTL code alone.

## Results to record (do not fill with guesses)

| Metric | Vivado observed value |
|---|---|
| Synthesis status, warnings | PENDING |
| Device | `xc7a35ticsg324-1L` |
| Clock constraint | 10.000 ns (100 MHz) |
| DSP48E1 | PENDING |
| LUT | PENDING |
| FF | PENDING |
| BRAM | PENDING |
| Post-synthesis WNS, unconstrained paths | PENDING |
| Tool version, Git commit | PENDING |

**Interpretation:** This clock-only core has no external I/O delays and no physical board pin assignments; those missing constraints will appear as unconstrained paths or associated warnings. Read post-synthesis timing as a preliminary logic/path check only. Actual board timing closure, input/output constraints, place-and-route, UART and FPGA hardware results must be measured after completing the top-level design.

## Acceptance gate

- [ ] The FIR-only top synthesizes successfully for `xc7a35ticsg324-1L`.
- [ ] Saved Vivado utilization and timing reports are readable.
- [ ] DSP48E1 inference and any unexpected resource mapping are documented.
- [ ] Warnings and the limitation of clock-only constraints are recorded.
- [ ] Physical FPGA or routed timing is **not** claimed without evidence.

At this point the standalone synthesis investigation can be marked complete. The broader project M2 implementation gate and M3 hardware gate remain separate.

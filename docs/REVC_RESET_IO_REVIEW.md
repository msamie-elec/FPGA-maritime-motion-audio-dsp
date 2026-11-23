# RevC reset and asynchronous I/O engineering review (21 November 2026)

## Source evidence and scope

Latest user-supplied **RevB routed** reports are preserved at `evidence/reference_2026-11-21_revb/` (Vivado 2025.2.1, 21 November 11:39). RevB WNS +1.889 ns; WHS +0.037 ns; LUT 633; FF 858; 1 DSP48E1; 2 RAMB18; on-chip vectorless power **0.069 W (estimate)**. No new RevC implementation or board measurements are claimed.

The RevB DRC had `REQP-1840` on `u_result_ram/mem_reg/ENARDEN` driven by **`u_reset_sync/stages_reg[2]` with asynchronous set/reset**. A fourth, clocked reset-output register in RevB did not prevent Vivado from optimising logic back to the async synchronizer register.

## RevC corrective design

`rtl/reset_sync.sv` uses three **plain, rising-edge clocked FFs**, no `posedge button_reset` / `negedge button_reset` in any sensitivity list. The unsynchronised BTN0 only reaches the first register's **D** pin. `ASYNC_REG=TRUE` and `SHREG_EXTRACT=NO` retain real FFs and encourage close placement; the reset output is the third **synchronous** stage. Artix-7 INIT=1 for all three FFs holds internal reset after configuration before the first three clocks. **Assertion and release can take three cycles** (30 ns @ 100 MHz), so very short external pulses are not guaranteed to reset the design. This is acceptable for manually pressed BTN0, but not automatically a suitable architecture for system-wide asynchronous safety requirements.

This removes the RTL mechanism that caused `REQP-1840`, but **the only authoritative confirmation is a new Vivado routed `report_drc`**. The post-route build script now **fails the release gate** if `REQP-1840` or `CFGBVS-1` is found. The report is still saved for troubleshooting. No DRC warnings are silently waived.

### Verification added

- `tb/tb_reset_sync.sv` checks configured startup, three-cycle assertion/release, no asynchronous reset glitches, a short pulse, and repeated BTN0 operation.
- `tb/tb_maritime_uart_top.sv` sends a partial UART request, asserts reset, verifies UART/LED idle, then performs a new bit-exact UART request.
- `hardware/sim/scripts/run_maritime_xsim.ps1` now runs both UART and reset self-checking XSim tops. `hardware/sim/scripts/run_maritime_sim.sh` offers equivalent optional Icarus regression.
- After running the **new** bitstream, repeat mid-job BTN0 reset, max 512-sample motion and audio jobs, cold/reset/soak trials and bit-exact host verification. Prior physical results apply only to prior builds.

## External I/O constraint audit

`constraints/arty_a7_35_maritime.xdc` specifies Digilent's Artix-7 100 MHz clock (E3, 10 ns), BTN0 (D9), USB-UART input/output (A9/D10), and four LEDs (H5/J5/T9/T10). It also sets board configuration bank settings `CFGBVS VCCO` / `CONFIG_VOLTAGE 3.3`; `CFGBVS-1` was absent in the latest RevB report.

The two external inputs (`uart_rxd_in`, `btn_reset`) are asynchronous to `CLK100MHZ`, are explicitly covered by **named** `set_false_path -from` exceptions, and are synchronised at RTL (UART two FFs, BTN0 three FFs). Five outputs (UART TX, four LEDs) go to a free-running USB-UART receiver or human indicators; **named** `set_false_path -to` exceptions exclude external source-synchronous output setup analysis, which has no meaningful common-clock relationship. No fabricated input/output delays are introduced. These exceptions do **not** verify electrical voltage/baud/bit-cell timing and should not be copied to a synchronous external interface.

**Release evidence still required:** use XSim UART edge/stop/CRC tests and physical 115200 8N1 round trips. Review `report_timing_summary -report_unconstrained`, `report_methodology`, and `report_drc` to ensure there are no unconstrained *internal* endpoints. External I/O electrical board compatibility comes from Digilent schematic/master XDC and practical hardware tests; timing exceptions are a documented interface assumption, **not full I/O sign-off**.

## Nonblocking post-route items

`DPIP-1` twice + `DPOP-1` once are DSP pipelining *optimisation recommendations*: the sequential 17-tap FIR is registered and timing passed at 100 MHz in RevB. Adding DSP pipelines changes output latency, control sequencing and PPA tradeoffs; do not change without a new test plan. `SYNTH-6` reports the output register not absorbed into one RAM primitive; a performance optimisation option, not an excuse to modify RAM control semantics. RevB vectorless `report_power` warns about switching/activity assumptions on high-fanout reset nets; do not equate the 0.069 W estimate with measured board power.

## Acceptance checklist for RevC

1. Python host tests: PASS from current RevC source.
2. XSim `MARITIME_RESET_SYNC_REGRESSION_PASS` and `MARITIME_UART_FIR_REGRESSION_PASS`: PENDING until run on Windows/Vivado.
3. Routed `REQP-1840` absent, `CFGBVS-1` absent, WNS/WHS >=0: PENDING until new Vivado build.
4. Source-linked bitstream SHA256 + bit-exact USB-UART tests and manual reset/cold/soak: PENDING on Arty A7.
5. Publication: only after steps 2–4 are reviewed, with remaining DSP and I/O exceptions disclosed.

## References

- AMD Vivado UG949, Synchronous Reset vs Asynchronous Reset: https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Synchronous-Reset-vs.-Asynchronous-Reset
- AMD UG901, ASYNC_REG: https://docs.amd.com/r/en-US/ug901-vivado-synthesis/ASYNC_REG
- Digilent master pin XDC: https://github.com/Digilent/digilent-xdc/blob/master/Arty-A7-35-Master.xdc

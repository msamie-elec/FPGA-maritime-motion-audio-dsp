# Arty A7 Maritime DSP — Post-Route Review

**Assessment date:** 17 November 2026  
**Tool:** AMD Vivado 2025.2.1  
**Top level:** `arty_a7_maritime_top`  
**Device:** `xc7a35ticsg324-1L`  
**Evidence:** four original routed/synthesised reports supplied by the design owner; no hardware tests supplied yet.

## Summary

**Vivado synthesis, placement, routing, DRC and bitstream generation completed**, and all *currently specified* timing constraints were met. The design is a promising candidate for board-level smoke testing, but it is **not yet hardware-verified or sign-off ready**: its reports contain six DRC warnings and external I/O timing is not fully constrained.

| Metric | Measured report value | Note |
|---|---:|---|
| Clock | 100.000 MHz (10.000 ns period) | single clock `sys_clk_pin` |
| Routed setup WNS | **+1.419 ns** | no setup-failing endpoints |
| Routed setup TNS | 0 ns | 2704 endpoints |
| Routed hold WHS | **+0.037 ns** | positive, but small margin |
| Routed hold THS | 0 ns | no hold-failing endpoints |
| Routed pulse width WPWS | +4.500 ns | no failures |
| LUT | **618 / 20800** | 2.97% |
| Registers | **856 / 41600** | 2.06% |
| DSP48E1 | **1 / 90** | 1.11%; expected time-shared arithmetic |
| RAMB18E1 | **2 / 100** | 2%; equal to one 36Kb BRAM tile |
| Bonded IOB | **8 / 210** | 3.81% |
| Bitstream generation | Completed | user console output |

## DRC audit

The routed DRC report finds **six warning instances**, **no DRC errors**:

| Rule | Instances | Engineering interpretation | Action |
|---|---:|---|---|
| `CFGBVS-1` | 1 | Configuration-bank voltage metadata not explicitly set | Add correct board-specific `CFGBVS` and `CONFIG_VOLTAGE` properties before release; verify against schematic/reference |
| `DPIP-1` | 2 | DSP48 A/B inputs not fully pipelined | Performance optimisation; may remain if 100 MHz and power/throughput goals are met |
| `DPOP-1` | 1 | DSP48 output PREG disabled | Assess after functional board tests; optional pipelining changes require RTL latency re-verification |
| `REQP-1840` | 2 | BRAM controls have upstream asynchronously reset register (reset synchronizer) | Investigate reset-domain/BRAM-control safety, verify repeated reset/recovery; prefer synchronously controlled RAM enable/reset logic |

No warning is being ignored as a matter of policy. The reported `REQP-1840` concerns BRAM reset/control behavior, **not** an error observed in the data. The current state is a *risk to investigate*, not evidence of memory corruption.

### I/O timing completeness

The routed timing report explicitly lists `TIMING-18` (seven missing delays): **2 input ports and 5 output ports without I/O delays**. It also reports **zero internal endpoints unconstrained** and the full set of setup/hold constraints met for the clocked paths it analyzed. For asynchronous UART and push-button inputs, standard synchronous board-interface delay constraints may not apply; document and constrain/synchronize them appropriately, rather than inventing arbitrary delays. Similarly, LEDs may be treated as asynchronous human-visible outputs with rationale. A future constraints audit should distinguish deliberate asynchronous I/O paths from accidentally unconstrained interfaces.

### Test readiness and sequence

1. Confirm the Arty A7 is exactly the intended device/board and that USB programming and UART ports are identified.
2. With the PC and FPGA grounded and normal USB connection, program the bitstream from the successfully built local `build/vivado_maritime_a7/maritime_a7.runs/impl_1/arty_a7_maritime_top.bit`. No external wiring is required.
3. Confirm LED0 ready-state and check reset button behavior.
4. Run `host/hardware_smoke.py --port COMx` for three bit-exact jobs. **A passing COM/CRC response alone is not enough**; the test compares actual returned FIR samples to the Python model.
5. Run `host/stabilize_video.py --out build/maritime_hardware --port COMx`. This **must** compare all FPGA-returned trajectory samples to the reference before labeling video as FPGA-verified.
6. Preserve actual `metrics.json`, MP4, console transcript, device identification and all routed reports. Treat the software-only prior video as separately labeled.
7. After board-level functional proof, address remaining reset/constraint warnings and record final rerouted metrics for the release candidate.

To consolidate steps 4–6, copy the accompanying `scripts/run_hardware_validation.ps1` into the `scripts` directory of the **same local project** used for this bitstream, and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_hardware_validation.ps1 -Port COM6
```

Replace `COM6` with the actual USB-UART port. The script **does not automatically program the board**. It creates an evidence transcript and runs both the hardware smoke suite and a real-FPGA video comparison, stopping on failed validation. It does not declare routed timing or DRC issues resolved.

## Sign-off decision

- **Bitstream build milestone:** PASS (provided routed reports and console).
- **100 MHz internal clock timing:** PASS for specified clocked paths.
- **DRC error count:** 0 errors; six remaining warnings to review.
- **External I/O constraint completeness:** NOT YET SIGNED OFF.
- **Physical FPGA UART/filter test:** NOT YET PERFORMED.
- **FPGA-backed maritime video:** NOT YET PERFORMED.
- **Public portfolio release:** NOT YET READY.

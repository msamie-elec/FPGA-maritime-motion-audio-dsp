# Integration v0.6 — Clean source baseline

**Status (18 November 2026):** source consolidation and software/RTL development candidate; *not* a final acceptance of video stabilisation quality.

This branch combines the reusable 17-tap FIR, Artix-7 UART+buffering hardware, board-top constraint/build Tcl, Python FPGA protocol and host client, desktop GUI v0.6, the operators' Help UI, natural-footage import, frequency and motion plots, independent image-jitter measurement, numerical tests, and the previously collected Vivado reports.

## Evidence boundaries

- User-reported hardware evidence on 17 November 2026: Artix-7 bitstream generated successfully, timing passed 100 MHz internally, physical **COM4** UART/FIR test returned bit-exact output for three jobs, and a synthetic maritime motion-video test passed. That is **CLI validation**, not proof that v0.6 desktop GUI communication passed.
- This integration snapshot: Python software regression **30 passed** on 18 November 2026 in the build environment. No new Vivado routing or physical-board run has occurred since assembling this snapshot.
- User observed virtually identical original/filtered maritime videos. **This is an open issue**, not marked fixed by a clean checkout.
- Existing FIR does **2D translation-only (X/Y)** motion smoothing; it does not compensate ship-camera roll, perspective, target motion or image blur.
- The motion-reduction percentage computed from estimated motion is a diagnostic, not proof of improved displayed image quality. Use the independent image-stability metric, original/after video, and any inconclusive flags.
- No recorded third-party video is included: provenance and public redistributability are not verified.

## Fresh installation (new directory; do not merge old `_3` folders)

1. GitHub: switch to this `integration-v0.6` branch, select **Code → Download ZIP**; extract to a **new, shorter** folder e.g. `C:\FPGA\maritime_v06`.
2. From PowerShell opened at the extracted root:

   ```powershell
   python -m pip install -r .\host\requirements.txt
   powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
   powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
   ```

3. To rebuild the FPGA project from fresh source (optional if board already programmed): close Vivado GUI, run

   ```powershell
   & "C:\AMDDesignTools\2025.2.1\Vivado\bin\vivado.bat" -mode batch -source scripts/build_maritime_bitstream.tcl
   ```

4. Use Vivado Hardware Manager to program `build\vivado_maritime_a7\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit`. Connect COM4 (recheck with `python -m serial.tools.list_ports`).
5. In GUI, use **Verify FPGA connection & FIR**, **Open video**, **Stabilise Video Using FPGA**, and examine **Independent image jitter** and the original/filtered videos.

The compile/build/board checks must be repeated after downloading this branch before it can be called verified on a clean workstation.

## Outstanding verification before portfolio release

- [ ] Confirm clean checkout Windows Python/GUI regression and v0.6 GUI usability
- [ ] Confirm Vivado UART-to-FIR RTL regression and routed 100 MHz implementation on clean checkout
- [ ] Verify v0.6 GUI to physical COM4 board (not merely CLI hardware smoke test)
- [ ] Demonstrate significant **independent** image-motion reduction on a naturally shaky recorded maritime video
- [ ] Assess rotation compensation and crop/edge handling; document negative cases and failures
- [ ] Copy signed-off source-identified test artifacts/measurements into evidence (no stale logs or unlicensed video)

For measured test limitations see [Video stabilisation diagnostics](VIDEO_STABILISATION_DIAGNOSTICS.md).

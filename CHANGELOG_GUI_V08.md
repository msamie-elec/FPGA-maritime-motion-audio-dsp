# v0.8 — Simplified three-tab GUI

- Replaced the vertically stacked video-and-metrics workspace with **Implementation / Assessment / Help**.
- Moved necessary controls onto **one row**, with smaller Segoe UI fonts and tighter spacing.
- Allocated the remaining Implementation area to the **largest practical synchronized video displays**.
- Gave motion curves, spectrum, independent image jitter and logs one **large Assessment viewport** each.
- Embedded readable guidance and FPGA programming instructions in the **Help** tab.
- Kept original-recording preparation, synthetic test clips and trajectory CSV import under **File**.
- Default smoothing changed to **Normal**; Strong remains user-selectable and explained.
- Preserved RTL, coefficients, serial protocol, Vivado constraints/build scripts, and physical hardware implementation.

**Verification:** 35/35 Python tests PASS; Linux desktop layout and software-preview smoke PASS. Windows physical Arty A7 GUI validation PENDING; no new hardware pass claim.

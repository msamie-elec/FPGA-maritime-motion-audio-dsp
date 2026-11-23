# Measured FPGA XADC snapshots — 23 November 2026

This directory contains the operator-supplied CSV transcribed **unchanged** from
Vivado Hardware Manager and a derived summary. `source` identifies actual XADC
readings, not an FPGA RTL thermal-monitoring block. Temperature was read via JTAG
and does **not** depend on a custom XADC instance in the design.

| Operator label | Samples | Mean die °C | Range °C |
|---|---:|---:|---:|
| Idle | 14 | 31.871 | 31.6–32.0 |
| Post-processing | 20 | 32.065 | 31.7–32.4 |
| Soak-end label | 2 | 31.900 | 31.9–31.9 |

**All 36 snapshots: 31.6–32.4°C.** The 0.194°C difference between the
post-processing and idle sample means is descriptive only: ambient conditions,
sampling cadence and elapsed idle time were not controlled. The two older
`soak_end` labels do not establish a measured soak. No continuous workload
trace, temperature peak, controlled hot test or power measurement is claimed.

The 15-minute FPGA UART reliability campaign is documented separately.
The earlier COM4 denied-access soak attempt is kept in the engineering history.

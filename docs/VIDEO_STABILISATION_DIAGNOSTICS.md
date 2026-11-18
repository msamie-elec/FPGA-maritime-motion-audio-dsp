# Why the original and stabilised videos may look nearly identical

**Current status: unresolved engineering issue, not a GUI installation issue alone.**

The low-level Artix-7 FIR has produced bit-exact numerical results. This verifies the Q16.8 FIR calculation, not that the estimated camera motion and chosen correction improve an arbitrary real video.

## Architecture and limitations

1. The host estimates an X/Y camera trajectory using OpenCV feature tracking and RANSAC.
2. A fixed 17-tap low-pass FIR smooths the trajectory. The FPGA receives **only two streams of motion numbers, not image pixels**.
3. OpenCV warps each frame by `smoothed - measured` X/Y displacement. This does **not** undo horizon rotation, rolling shutter, camera zoom, perspective and independently moving ships.
4. If motion is already slow/smooth, the FIR correction may be only a few pixels or less. That can look unchanged even though the FPGA output is bit-exact.
5. A fast-moving foreground or unstable sea wave pattern can impair motion estimation. Stationary background is sometimes sparse in sea footage.

## Evidence from candidate maritime videos (software-reference, not FPGA)

| Candidate | FIR X high-frequency reduction | FIR Y high-frequency reduction | Independent image-jitter reduction | Interpretation |
|---|---:|---:|---:|---|
| Video 4, chosen 1–6 sec segment | 25.8% | 23.4% | **79.8%** | Better candidate, still inspect visual result |
| Video 6, 16–21 sec close-ship segment | 7.8% | 5.7% | **38.6%** | Some improvement; FIR coordinate smoothing itself is modest |
| Video 7, 19–24 sec storm segment | 2.4% | 7.9% | **−128.9%** | Worse visual-jitter measurement; **do not use as success case** |

These measurements were saved by the software-reference GUI pipeline during candidate selection, not measured on the physical FPGA. They are noisy image-registration proxies and may not match perception.

## Next algorithm work (separate from clean-source consolidation)

- Add measured per-frame X/Y and rotation, with explicit confidence/feature-count diagnostics and a residual correction magnitude plot.
- Add **roll-angle estimation and correction**, ideally testing that correction independently before expanding FPGA RTL; the existing serial FIR may smooth an angle trajectory as a third job if fixed-point range/scaling and timing are validated.
- Display original and corrected video in a zoomed comparison with matched crop and optional difference overlay; avoid blur as a substitute for stabilisation.
- Improve adaptive motion estimation for weak-texture sea/horizon and moving objects. Flag low-quality estimates instead of overstating improvement.
- Retain a no-shake/no-op negative test and report when correcting footage makes it worse.

This diagnostic does **not** claim a bug in existing FPGA arithmetic. A firmware/GUI source mismatch remains plausible but should be checked using a fresh clean checkout and GUI-to-board test.

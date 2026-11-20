# GUI v0.8.1 — Playback reliability update

**Scope:** Desktop GUI only. The existing Arty A7 bitstream, RTL, UART protocol, FIR coefficients, numeric filtering and stabilisation code are unchanged.

## Fixed user-reported playback issues

1. **Original video playable before processing.** Selecting `Open video`, importing genuine footage, or generating the synthetic lab clip opens an independent original-only player in the left panel. The right panel remains a clearly labelled placeholder until a processing result is available. No firmware, COM port or processing mode is required to preview the original footage.
2. **Replay after the end.** When a source or processed comparison reaches its last frame, `Play` becomes `Replay`. Clicking it resets to frame zero and starts again. Playback works repeatedly without re-running the FIR or reconstructing video.
3. **Pause and seek.** Pausing stops scheduled frames; dragging the seek slider pauses playback and displays the selected source/comparison frame. Releasing at the end enables replay.
4. **Safe source switching.** Choosing another video, pressing Reset view, or finishing processing releases the previous decoder and cancels old Tk playback timers. `Reset view` restores the original-only preview if a source remains selected.
5. **Comparison remains synchronized.** After processing, both halves are decoded from the same already-rendered side-by-side MP4; no independent clock drift or separate decoder state is introduced.

## Verification and limitations

- Three new GUI playback tests cover original-only preview before processing, replay after final frame and seeking, and switching video/reset during playback.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1` on Windows. Run `xvfb-run -a python -m pytest -q tests/test_gui_playback.py` in a Linux desktop test environment.
- This is a GUI reliability fix. It does **not** demonstrate a new improvement in video stabilisation quality, and **does not** constitute new FPGA hardware verification.
- Input video still must satisfy v0.8's supported 30-fps, resolution, duration and codec requirements, or be prepared using the File menu.

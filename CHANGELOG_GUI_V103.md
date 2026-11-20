# GUI playback regression timing fix — v1.0.3 (2026-11-20)

## Problem

On Windows, `tests/test_gui_playback.py::test_open_video_can_play_before_filtering` expected exactly one video frame from a real-time playback tick. The GUI intentionally follows elapsed wall-clock time to remain aligned with the soundtrack; slower Windows rendering and decoding can legitimately show frame 3 instead of frame 1.

## Correction

The playback test now freezes the clock during its synthetic tick, permitting exactly one deterministic presentation frame. No FIR, UART, bitstream, audio filter, or video/audio playback source files have changed.

## Tested in development container

- Desktop/GUI and processing regression: 56/56 passed.
- Unified video/audio tests: 6/6 passed.
- Split into two processes to avoid a single-suite stall; Windows must still run the combined `scripts/run_gui_tests.ps1` command.

## Windows

Extract the small ZIP to the current project folder with `tests/` aligned to `host/`, replacing only `tests/test_gui_playback.py`.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

No bitstream regeneration is required. To test sound on Windows, open the included video and press Play, then compare `Original` and `Filtered` after a software preview. This has not been physically speaker-tested here.

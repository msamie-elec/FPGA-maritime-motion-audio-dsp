# GUI v0.8 — three-tab operator interface

**Status (20 November 2026):** GUI development candidate. 35/35 host Python tests and Linux/Xvfb desktop smoke and software video-preview tests PASS. **Physical Windows COM4 GUI verification not yet completed.** All FPGA RTL, XDC, coefficient ROM, bitstream scripts and physical UART protocol are unchanged.

## Layout

**Implementation:** One compact toolbar: Open video, Reset view, COM-port selection, Detect ports, Verify FPGA, Stabilise using FPGA, Software preview, and Smoothing. Below this, nearly all free space is assigned to synchronized original and corrected video panels and a shared seek/play bar. Video retains original aspect ratio and responds to window resizing.

**Assessment:** Full-window assessment with compact X/Y/roll/frame/time values, independent image-stability and hardware-validation status, then a **single large plot** selected using Motion curves, Frequency spectrum, Image stability, or Evidence log. Change axes X/Y/ROLL for trajectory and spectrum views. No plot competes with video area for vertical space.

**Help:** A dedicated scrollable tab with operator quick start, button explanations, Vivado programming and COM-port setup, and verification limitations. Press F1 to open it.

Special-purpose laboratory features remain available via the File menu: Prepare original recording, Generate synthetic clip, and Load synthetic lab trajectory CSV.

## Smoothing profile

- **Normal (default):** one 17-tap FIR pass for each X/Y/roll axis, three FPGA jobs.
- **Strong:** two successive FIR passes for each axis, six FPGA jobs. This can produce stronger attenuation but may suppress intentional motion and increase cropping. Strong is **not always better**.

The bitstream is identical in both modes. The Python client checks every FPGA-returned value bit-exactly against the independent numerical model.

## Build/launch on Windows

From a **fresh clean** download of this branch, not mixed with earlier copies:

```powershell
python -m pip install -r .\host\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

The FPGA must already be programmed with the compatible `arty_a7_maritime_top.bit`. To rebuild, close Vivado GUI and run:

```powershell
& "C:\AMDDesignTools\2025.2.1\Vivado\bin\vivado.bat" -mode batch -source scripts/build_maritime_bitstream.tcl
```

Program the generated bitstream through Vivado Hardware Manager. COM4 was observed on one development PC; detect the correct port each time.

## Evidence and limitations

35/35 host tests passed, and a completed **software-only** synthetic demo was displayed side by side with a full-size Assessment motion curve during a Linux desktop test. This is not physical FPGA proof. Independent image registration may be IMPROVED, WORSE or INCONCLUSIVE. Camera/scene motion problems are not solved merely by changing the GUI.

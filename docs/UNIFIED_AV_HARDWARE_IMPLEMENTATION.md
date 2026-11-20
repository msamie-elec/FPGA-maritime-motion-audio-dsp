# Arty A7-35T — Unified video + audio implementation

**Scope:** v1.0.3 integrated offline 3-axis camera-motion FIR and 16 kHz speech-band FIR. Both use the shared, multiplexed DSP datapath on one Artix-7 FPGA. Video decoding, motion estimation, image warping, audio decoding/encoding and MP4 creation remain on the host PC.

**Hardware status:** Not yet physically validated for dual bank. A completed Vivado build alone does not prove audio or video correctness.

## Before starting

- Start from the clean full v1.0.3 source plus the scripts in this package.
- Windows PowerShell, Python dependencies installed (`python -m pip install -r host/requirements.txt`).
- AMD Vivado 2025.2.1 at `C:\AMDDesignTools\2025.2.1\Vivado` (or pass `-VivadoBin`), an Arty A7-35T and a USB cable.
- Close the Vivado GUI project if it is open. A fresh `build/vivado_maritime_a7` project will be generated.
- Do not run the old video-only FPGA bitstream for audio; `job_id[7]` must select the new audio coefficient ROM.

## 1. Local simulation + FPGA bitstream (one command)

From the directory containing `rtl/`, `host/`, `scripts/`, `videos/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_unified_av_fpga.ps1
```

The command checks the dual-bank RTL coefficient ROM, runs Python regression in two groups, runs Vivado XSim UART/FIR simulation, synthesizes and places/routes the board design, writes a bitstream and collects timing, DRC and utilization reports. It writes a timestamped transcript and metadata under `evidence/build/`.

Expected final line: `UNIFIED_AV_BUILD_DONE`. **This indicates a produced bitstream, not successful hardware programming or timing/DRC sign-off.** Review the routed reports before declaring implementation complete.

Bitstream path:

```text
build/vivado_maritime_a7/maritime_a7.runs/impl_1/arty_a7_maritime_top.bit
```

Vivado design:

```text
build/vivado_maritime_a7/maritime_a7.xpr
```

## 2. Program the board

1. Attach the Arty A7 by USB and power it.
2. Open Vivado Hardware Manager, **Open target / Auto Connect**, and confirm the device is `xc7a35t`.
3. **Program Device** with the *new bitstream above*, not the old video-only `.bit`.
4. Confirm startup is complete. No ILA core is required for this design.
5. Check USB-UART COM port in Device Manager or `python -m serial.tools.list_ports`. `COM4` was used in earlier physical tests; verify the current port.
6. Close any GUI or serial-monitor window holding that port before the command-line hardware test.

## 3. Hardware verification (one command)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_unified_av_hardware.ps1 -Port COM4
```

The script checks four physical UART cases (`motion → audio → audio mixed-sign → motion`) against independent Python FIR calculations. Then it processes `videos/03_Unified_Quick_Test_3s.mp4` with **both** camera-motion and speech-band FIR on the board, verifies the FPGA-returned values bit for bit, and outputs a single MP4 with processed video and audio. The result lives in `videos/hrd/unified_av_<timestamp>/`; engineering evidence lives in `evidence/hardware/unified_av_<timestamp>/`.

Expected markers: `DUAL_BANK_PHYSICAL_FPGA_PASS` and `UNIFIED_AV_PHYSICAL_FPGA_PASS`.

If FPGA communication fails, stop and retain the console transcript. Wrong-bank responses are detected by numerical mismatch. Do not fall back to software and label it hardware.

## 4. GUI after successful hardware verification

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

Open the short source, select **Video + Audio**, choose your COM port, run Verify FPGA and **Process on FPGA**, then use **Audio: Filtered** to listen. The separate external-player option remains available. Note that filtering primarily attenuates high-frequency noise; low-frequency engine/wind noise may remain.

## Limitations to report honestly

- 30-frame/s video **motion trajectories**, not real-time pixel streaming to the board.
- 16 kHz mono **buffered audio**, not a live microphone/ADC audio interface.
- Existing audio FIR is a 17-tap 3.2 kHz low-pass; voice intelligibility is not established by spectral reduction alone.
- A 30-second source requires many USB-UART batches and is a later load/stability test.
- Check routed timing and DRC reports, especially asynchronous-input and BRAM control warnings. Do not interpret positive WNS alone as full I/O sign-off.

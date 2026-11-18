# Reproducible development & demo

All steps should run from repository root. Windows: `python -m pip install -r host/requirements.txt`.

1. **Software-only design preview, no FPGA claims:** `python host/stabilize_video.py --out build/maritime_demo`. Outputs a labelled split-screen MP4, synthetic ground truth and `metrics.json`.
2. **Python unit tests:** `python -m pytest -q tests/test_fixed_point.py tests/test_serial_protocol.py tests/test_synthetic_maritime.py`.
3. **Vivado XSim full UART+FIR RTL test:** `powershell -ExecutionPolicy Bypass -File scripts/run_maritime_xsim.ps1` in Vivado-enabled PowerShell.
4. **Board project:** `vivado -mode batch -source scripts/create_maritime_vivado.tcl` to inspect source hierarchy in GUI.
5. **Board bitstream / timing:** `vivado -mode batch -source scripts/build_maritime_bitstream.tcl` (close GUI first). Check implementation and report warnings before programming.
6. **Hardware video:** `python host/stabilize_video.py --out build/maritime_demo --port COM6` (replace COM6 with actual Arty UART port). This aborts if any returned FPGA sample differs from bit-exact Python reference.

The board top only requires clock, UART, a reset button and LEDs. Video pixels remain on the laptop; FPGA processes only motion vectors. Audio support remains a future release. No real camera stream over UART is claimed.

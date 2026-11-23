# Reproducible maritime video/audio tests

These are four **user-supplied, AI-generated clips**, not real maritime sea-trial footage. The exact video properties and SHA-256 hashes are in [the manifest](../videos/VIDEO_TEST_MANIFEST.json). Use the videos **without re-encoding** to reproduce the reference tests.

**Fast functional test:** Load `videos/03_Unified_Quick_Test_3s.mp4` in the GUI. Select `Video + Audio`. For software-only processing, select `Software preview`. For a physical FPGA test, connect Arty A7 at your assigned COM port, program the previously verified bitstream in Vivado, select `Verify FPGA` and `Process on FPGA`. The motion and audio FIRs operate in FPGA hardware; video warping and adaptive audio cleanup are **host-side**.

**Video-only tests:** Use `00_Maritime_Short_Original.mp4` or `01_Maritime_Short_Original.mp4`, select `Video only`, and compare Normal/Strong smoothing with the `Video Assessment` view. These two files have no audio tracks.

**Extended software/hardware tests:** Load `02_Maritime_Long_30s_With_Audio.mp4` to test GUI progress and cancellation. The FPGA UART design is buffered/non-real-time; a 30.2-second clip is *not* expected to process in 30.2 seconds.

**Audio assessment:** Use `02` or `03`, compare original/processed sound and spectral-band attenuation in `Audio Assessment`. Spectral band reduction does not demonstrate speech-intelligibility gain.

**Run the GUI (Windows PowerShell, repository root):**
```powershell
python -m pip install -r .\host\requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

Numerical RTL simulation, Vivado report and physical reliability commands are catalogued in [TEST_AND_VERIFICATION_COMMANDS.md](TEST_AND_VERIFICATION_COMMANDS.md). Record bitstream provenance, test parameters and the original media hashes. Keep processed media in `videos/sim/` or `videos/hrd/`, not the source video folder.

**Publication:** Some clips retain Synthesia branding. Source-code licence and AI-video usage licences are distinct; verify the video-generation subscription's permission to redistribute before making the private repository public or using test clips in paid promotional material.

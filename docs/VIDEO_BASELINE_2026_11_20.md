# Video stabilisation baseline — 20 November 2026

This is the latest integrated **video** baseline before the separate audio-noise-removal development phase.

## Confirmed

- User reports that the GUI and 30.2-second media workflow work on the Windows workstation. The *embedded* Tk/OpenCV video displays frames **without sound**, by design; `Play MP4 with audio` opens a source or output MP4 in a system media player.
- Previously supplied COM4 evidence (17 Nov 2026) confirms three physical batch-UART FIR jobs and synthetic video trajectory checks, not a fresh physical test for the longer 906-frame processing path.
- Software regression rerun in the development container (20 Nov 2026): **43/43 PASS** on the non-display numerical/video test suite, including long-input overlap and AAC-preservation test.
- Input MP4 and output simulation/hardware artifacts are organised as `videos/`, `videos/sim/`, and `videos/hrd/`. The user-provided video binaries are **not committed** to GitHub pending their redistribution rights.

## Unresolved limitations

- Full 906-frame physical COM4 job, including multiple overlapping FIR packets: not yet evidenced as passed.
- No microphone/audio ADC interface or realtime audio streaming: PC handles video/audio files; FPGA processes serialized motion data.
- Audio in the in-app Tk frame player is silent; original AAC is preserved when exported and played through an external media player.
- The present motion FIR has a 30 Hz trajectory sample rate and 2.5 Hz cutoff; it is **not an audio denoiser**.
- The quality of visual stabilisation on difficult scenes is variable; do not claim that every maritime clip improves.

## Next development

Work in a separate `feature/audio-fir-v0.9` branch with an independently designed audio filter bank, 16 kHz mono PCM conversion, software-reference processing and an explicit future physical FPGA verification gate. Do not label software output as physical hardware result. Preserve the known-good video baseline and full source history.

## Reproduction

```powershell
python -m pip install -r .\host\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

Use Vivado Hardware Manager to load the matching earlier board bitstream if it has lost configuration. Long-video COM4 verification must still be run independently.

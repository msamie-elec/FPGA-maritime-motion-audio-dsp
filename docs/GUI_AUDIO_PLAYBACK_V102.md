# GUI v1.0.2 — synchronized audio/video playback (Windows)

## Problem and correction

The v1.0.1 Tkinter/OpenCV player rendered only video frames. The combined MP4 did contain AAC audio, but the in-app **Play** and **Replay** buttons ignored it. `Play MP4 with audio` opened a separate Windows player as a workaround.

The GUI now plays one selected audio track **with** the video presentation clock. The audio dropdown offers Original, Filtered and Mute. Before filtering, Original is selected; after Video + Audio filtering, Filtered is selected automatically. Pause and seeking stop audio; press Play to resume from the selected time. Replay restarts both video and audio.

On Windows, the system uses the built-in WinMM/MCI waveaudio subsystem. FFmpeg converts the MP4 AAC audio into a cached 16 kHz mono PCM WAV. When the filter has been run, the original and cleaned WAVs from the result directory are used directly. The Tk video is scheduled from a monotonic presentation clock instead of counting GUI timer callbacks; this allows late frames to be skipped rather than causing increasing sound/video drift. There may still be device-dependent start latency; this is an **offline preview**, not a certified A/V synchronisation engine.

Only **one soundtrack** is played at a time despite two side-by-side images. Choose Filtered to hear cleaned sound or Original to hear the source. No acoustic output is streamed from the Arty A7 in real time; the FPGA produces buffered, numerically checked samples earlier in the processing workflow. On non-Windows platforms use `Play MP4 with audio` instead.

## Windows acceptance checklist

1. Run `scripts\run_gui_tests.ps1` and confirm all tests pass. The new tests use a fake speaker backend and do **not** prove Windows speaker output.
2. Open `videos\03_Unified_Quick_Test_3s.mp4`; choose Play **before** processing. Check that source audio is heard and stops when paused.
3. Choose Video + Audio and Software preview, then Play: default Audio=Filtered. Observe both images and hear the cleaned soundtrack.
4. Change Audio to Original while playing and compare. Select Mute and confirm silence.
5. Scrub, press Play and verify the audio resumes at the corresponding time. Replay after the end.
6. Test `Play MP4 with audio` as an external fallback.
7. For the physical FPGA route, continue to require the new dual-bank bitstream and actual COM4 verification. GUI audio playback alone is not an FPGA hardware acceptance test.

## Limitations

- The computer's sound output must be correctly configured; WinMM playback is Windows-only.
- MP4 conversion is cached for the session; selecting Play may briefly decode the soundtrack the first time.
- The 17-tap 3.2 kHz audio FIR only suppresses out-of-band noise. It cannot guarantee noise-free speech.
- This change does not modify the RTL or bitstream.

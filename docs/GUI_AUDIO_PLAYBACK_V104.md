# GUI audio playback recovery v1.0.4 (candidate)

## Symptom

On the Windows GUI, the source MP4 speaks normally until video/audio processing finishes; then both **Filtered** and **Original** soundtrack modes in the side-by-side viewer are silent. **Reset** restores source audio. The physical dual-bank FIR has separately passed bit-exact tests; this symptom does **not** demonstrate a hardware filtering failure.

## Changes

- Prefer `sounddevice`/PortAudio PCM16 playback over legacy Windows MCI for the embedded post-process media player. If PortAudio cannot open an output device, retry with the earlier Windows MCI backend, surfacing both errors if necessary.
- Keep MCI as a fallback when `sounddevice` is unavailable.
- Decode each MP4 soundtrack to WAV once and cache it. Use the existing output `audio_original.wav` and `audio_filtered.wav` for track selection.
- Log exact selected audio filename, backend and playback offset in **Assessment → Evidence log**. Display playback errors in the bottom status bar rather than silently continuing.
- When paused, changing the Audio selector only changes track choice: press **Play** to hear it. While playing, changing the selector restarts from the current video frame.

## Installation and Windows acceptance

Extract the small hotfix ZIP into the **same existing working** project folder, replacing the matching `host`, `tests` and `docs` files. Run:

```powershell
python -m pip install -r .\host\requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

1. Open `videos\03_Unified_Quick_Test_3s.mp4`, select **Audio: Original**, and press Play: audible soundtrack expected.
2. Run **Software preview**, then press Play in the result: **Filtered** soundtrack expected.
3. Change to **Original** during playback, and then change back to **Filtered**. Hear each soundtrack and observe status indicating current backend.
4. Repeat from **Replay** and test after a *hardware* run on the same dual-bank bitstream.
5. If silent, check the Windows Volume Mixer, verify output device, and inspect **Assessment → Evidence log** for `AUDIO PLAYBACK` or `AUDIO PLAYBACK FAILED`. Test `audio_original.wav` and `audio_filtered.wav` in the external Windows player to distinguish absent audio from playback-device issues.

No RTL, XDC, Vivado build or bitstream changes. This fix has software regression evidence; **Windows physical speaker output remains to be tested on the user's PC**.

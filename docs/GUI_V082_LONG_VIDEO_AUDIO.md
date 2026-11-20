# v0.8.2 — Long footage, audio and assessment provenance

**Source media location:** `videos/*.mp4`. The user's three test MP4 files are included in the separate complete downloadable ZIP but are not automatically committed to GitHub.

**Results:** `videos/sim/<timestamp>_software/` for software reference; `videos/hrd/<timestamp>_hardware/` for bit-exact physical FPGA runs. These generated directories are Git-ignored.

## GUI
- One-row order: Open video → Reset view → Software preview → COM → Detect ports → Verify FPGA → Stabilise using FPGA → Smoothing.
- Assessment displays the source video filename and explicit SOFTWARE REFERENCE / PHYSICAL FPGA / NOT RUN / PROCESSING status. A three-case connection check is not video validation.
- The GUI has large, separate Implementation, Assessment and Help tabs.

## Long-input architecture
- Host accepts up to 1,500 frames / 50 seconds at 30 fps, at most 1280×720.
- The Artix-7 UART/FIR still accepts at most 512 signed Q16.8 samples per job. Software divides each axis into <=496 NEW frame samples with 8 left and 8 right context samples. Every physical packet is checked against the continuous centred 17-tap Python reference, preserving correctness at chunk boundaries. Strong mode runs two such passes per axis.
- **The existing RTL and bitstream are unchanged.** This is buffered/offline processing, not a real-time FPGA video pipeline.
- Image-based stability checks stream cropped regions without caching full frames.

## Voice and sound
- Original source audio is retained in the exported comparison MP4 (AAC), without filtering.
- The embedded OpenCV/Tk preview is deliberately **silent**. Choose **Play MP4 with audio** to open the selected source or output video in the default system player.
- Noise removal and speech enhancement are planned for a later audio-DSP project milestone, not implemented here.

## User video 2 preparation
Original `2(1).mp4`: 34.7 seconds, 1920×1080, 30 fps, AAC. The accompanying complete ZIP contains `videos/02_Maritime_Long_30s_With_Audio.mp4`: 0.0–30.2 seconds, 906 frames, 960×540 at 30 fps, original AAC sound included. The promotional final screen begins near 31 seconds, and is excluded. This appears AI-generated and includes several scene cuts. Full 906-frame software-only processing completed with audio retained, but independent visual-stability assessment was INCONCLUSIVE. No physical long-video hardware claim has been made.

## Verification
- Existing numerical tests and mock-FPGA overlapping packet tests pass in the packaged development environment.
- Physical COM4 multi-packet and GUI Windows playback require local validation.
- Only use bit-exact FPGA-returned values to label a video PHYSICAL FPGA VERIFIED.

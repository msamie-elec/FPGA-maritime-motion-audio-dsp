# Source videos and results

Place original or prepared, 30-fps compatible input MP4s directly in `videos/`.
Do not put source material in `build/`, which is an expendable Vivado/temporary-work directory.

- `videos/00_Maritime_Short_Original.mp4`
- `videos/01_Maritime_Short_Original.mp4`
- `videos/02_Maritime_Long_30s_With_Audio.mp4`
- `videos/sim/<run-id>_software/`: each software-reference run and its evidence
- `videos/hrd/<run-id>_hardware/`: actual hardware-returned data, verified bit-exact

Output subfolders are ignored by Git, but are saved locally. Raw videos are user-provided AI-origin test assets; check redistribution rights before publishing those MP4 files to a public GitHub repository.

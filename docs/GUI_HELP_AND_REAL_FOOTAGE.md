# Maritime FPGA DSP — Interactive Help & Real-Video Test Cases (v0.4)

**Status:** Software GUI and preparation workflow tested. **No assertion that original Pexels MP4s are bundled or that the new GUI has been physically tested against the FPGA.** The existing v0.3/v0.2 bitstream does not need to change.

## Quick start — Arty A7 hardware

1. Connect your **Arty A7-35T** by USB and ensure it is powered.
2. In **Vivado 2025.2.1** open **Hardware Manager → Open Target → Auto Connect**.
3. Select `xc7a35t_0` and choose **Program Device** with the proven bitstream:
   `build/vivado_maritime_a7/maritime_a7.runs/impl_1/arty_a7_maritime_top.bit`.
4. Return to the GUI. Click **Detect COM ports** and choose the board's port. It was **COM4** on the development workstation; this is *not* a universal port designation.
5. Click **Verify FPGA connection & FIR**. It sends three numerical jobs and checks results against the exact Python model. The output must show **3/3 PASS** before using the physical mode.
6. Load a short video (or import prepared real footage as described below), then click **Stabilise Video Using FPGA**.
7. When finished, play the **same time/frame** in both panes. Check X/Y trajectories, frequency spectra, verification text, and **Open result folder** for MP4, plots, CSV and metrics.

**Programming state:** the GUI does not program the FPGA. The Arty may need reprogramming after power-off or loading a different design. **BTN0** resets the active RTL; new FIR processing jobs automatically reset FIR history; **Reset view** only clears GUI output.

## What every button does

| Control | Purpose |
|---|---|
| **Open video…** | Load a compatible MP4/MOV/AVI/M4V from disk; estimate motion in OpenCV unless a CSV is attached |
| **Generate synthetic test video** | Create a simple cartoon/animation with *known* motion; **not real footage** |
| **Real ship footage…** | Open the two real-source options, browser links and import workflow |
| **Optional trajectory CSV…** | Select per-frame trajectory in signed Q16.8 samples; when present no motion estimation is attempted |
| **Reset view** | Clear displayed results; does **not** program or reset FPGA |
| **Detect COM ports** | Re-enumerate serial devices connected to Windows |
| **Verify FPGA connection & FIR** | Test three physical bit-exact FIR jobs: impulse, negative DC, mixed sign |
| **Stabilise Video Using FPGA** | Send trajectory to the real board, verify returned samples against Python, warp and display the video |
| **Software preview only** | Use software FIR without FPGA; not a hardware demonstration |
| **Play / Pause / Slider** | Synchronous before/after playback and navigation |
| **Camera motion curves / Motion frequency spectrum** | Plot original and filtered X/Y numerical trajectories and spectral content |
| **Evidence and log** | Show test messages and error details |
| **Open result folder** | Show MP4, plots, CSV and metrics saved by the previous run |
| **Help / Steps** or **Help → Help & complete instructions** | Open a scrollable guide for new users; includes hardware programming and real footage instructions |

## Two real-footage sources

**A. Ferry view with distant cargo ship**, Rahime Gül — [Pexels 28945771](https://www.pexels.com/video/silhouettes-on-ferry-with-cargo-ship-view-28945771/). Approx. 8 s, vertical 1080×1920, ~59.94 fps.

**B. Pilot boat alongside a cargo ship**, Alexander Grigorian — [Pexels 7397246](https://www.pexels.com/video/a-boat-sailing-alongside-a-cargo-ship-7397246/). Approx. 41 s, landscape 1920×1080, ~29.97 fps.

Pexels license: https://www.pexels.com/license/ . Credits are voluntary under its terms, but included here for professional traceability. Do not imply creator sponsorship or resell unmodified originals as stock video.

**Original media are not bundled.** Download each video from its own Pexels page using the site's **Free download** control, then use **Real ship footage… → Import downloaded MP4 and prepare**. This avoids stock footage licensing confusion and large GitHub/media downloads.

The GUI's preparer writes, for each source:

- `ferry_real_30fps.mp4` / `pilot_real_30fps.mp4`: trimmed, aspect-correct **genuine input video frames**, no injected motion.
- `ferry_real_with_injected_shake_30fps.mp4` / `pilot_real_with_injected_shake_30fps.mp4`: **the same genuine frames, but translated with artificial known X/Y shake** for a controlled hardware demonstration.
- `*_known_injected_motion.csv`: one signed Q16.8 X/Y trajectory pair per frame, as generated and known exactly.
- `PROVENANCE.json`: original file path, SHA-256, Pexels source/creator, output parameters and explicit declaration of the added synthetic shake.

The prepared videos are **150 frames, 30 fps, 960×540**, and compliant with the existing FIR UART limits. The vertical ferry source uses side bars to preserve composition. They are created in `build/real_maritime_clips/` (ignored by Git).

### Batch preparation without using the GUI

From the repository root on your Windows PC, after downloading both originals:

```powershell
python .\host\prepare_real_maritime_clips.py --ferry "C:\Videos\ferry_original.mp4" --pilot "C:\Videos\pilot_boat_original.mp4" --out "build\real_maritime_clips"
```

You can also pass just `--ferry` or `--pilot`. In the GUI click **Open video…** and choose the `*_with_injected_shake_30fps.mp4`, then select its matching `*_known_injected_motion.csv` before clicking **Stabilise Video Using FPGA**.

## Technical limitations and integrity

- Current FPGA filtering applies to **motion X/Y samples only**, not video pixels or video decompression.
- Laptop: decoding, optical-flow estimation (if no CSV), geometric frame correction, plotting, playback and export.
- Real source video does not necessarily include usable shipboard camera shake. The optional *injected* shake is a test disturbance, **not a claim of motion measured at sea**.
- Existing `motion_estimation.py` only supports **global translation**. Tilt/roll, perspective, zoom, parallax, blur and independent vessel movement remain unresolved.
- Software-only output is labelled **SOFTWARE REFERENCE**, never physical hardware proof.
- Only samples returned by physical FPGA and bit-exactly matched to the independent reference are labelled **PHYSICAL FPGA — VERIFIED**.
- GUI's performance reduction percentages describe a defined high-frequency **trajectory metric**, not a guarantee that arbitrary maritime footage is fully stabilised.
- Real-world footage and its authenticity cannot be established by file selection alone; verify that the downloaded input genuinely came from the credited Pexels page.


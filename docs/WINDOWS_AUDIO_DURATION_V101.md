# v1.0.1 — Windows AAC duration/short-video correction

## Observed failure

The Windows regression `test_combined_software_creates_single_av_output` showed `14976 >= 15600` failing; **56 other tests passed**. A one-second (30-frame) MP4 AAC fixture can return only 14,976 PCM16 samples after decoding on some FFmpeg platforms. At 16 kHz, this is a 1,024-sample/64 ms shortfall, consistent with AAC encoder priming and packet boundary differences. It is not evidence of incorrect FIR arithmetic.

## Correction

`host/unified_pipeline.py` aligns the decoded 16 kHz mono audio duration to the **actual decoded video frame interval**. If the audio ends early, only its trailing missing samples are zero-padded; if it runs longer, its tail is trimmed. Original audio content is not synthesized or modified except for normal FIR filtering and end alignment. The adjustment counts are written to `metrics.json` and `combined_metrics.json`. This prevents `-shortest` from unexpectedly truncating the finished video because the soundtrack was a packet short.

`tests/test_unified_pipeline_v10.py` checks exact frame/sample alignment; an additional negative fixture injects a one-AAC-packet shortfall and verifies the final output retains 30 frames and its WAV retains 16,000 samples.

## Test on Windows

Extract the hotfix ZIP into the **project root**, merge/replace `host/`, `tests/`, and `docs/` files. Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_gui_tests.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
```

The expected message is `MARITIME_GUI_SOFTWARE_REGRESSION_PASS`; the regression may show a different number of tests if older/newer tests are added. First choose Video + Audio and run Software preview on the supplied three-second source. Only then rebuild the dual-bank bitstream for physical testing.

**Do not apply this hotfix to the old video-only baseline.** It is specific to the v1.0 unified Audio+Video development candidate.

# Run GUI host-only regression; does not pretend to test the physical FPGA.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
# Run GUI/window tests and FFmpeg-heavy unified integration tests in separate
# Python processes. This also avoids a rare resource contention during teardown
# of the Tk player after media encoding on some desktops.
& python -m pytest -q verification/model/tests/test_fixed_point.py verification/system/tests/test_serial_protocol.py verification/system/tests/test_synthetic_maritime.py verification/system/tests/test_gui_pipeline.py verification/system/tests/test_natural_footage.py verification/system/tests/test_three_axis_v07.py verification/system/tests/test_gui_playback.py verification/system/tests/test_gui_audio_playback_v102.py verification/system/tests/test_gui_postprocess_audio_v104.py verification/system/tests/test_long_media_v082.py verification/model/tests/test_audio_fir_v09.py verification/system/tests/test_maritime_adaptive_v11.py
if ($LASTEXITCODE -ne 0) { throw 'GUI host regression failed' }
& python -m pytest -q verification/system/tests/test_unified_pipeline_v10.py
if ($LASTEXITCODE -ne 0) { throw 'Unified AV host regression failed' }
Write-Host 'MARITIME_GUI_SOFTWARE_REGRESSION_PASS (physical hardware GUI run separately required)'

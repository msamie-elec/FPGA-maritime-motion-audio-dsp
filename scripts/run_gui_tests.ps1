# Run GUI host-only regression; does not pretend to test the physical FPGA.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
& python -m pytest -q tests/test_fixed_point.py tests/test_serial_protocol.py tests/test_synthetic_maritime.py tests/test_gui_pipeline.py tests/test_natural_footage.py tests/test_three_axis_v07.py tests/test_gui_playback.py tests/test_long_media_v082.py tests/test_audio_fir_v09.py
if ($LASTEXITCODE -ne 0) { throw 'GUI host regression failed' }
Write-Host 'MARITIME_GUI_SOFTWARE_REGRESSION_PASS (physical hardware GUI run separately required)'

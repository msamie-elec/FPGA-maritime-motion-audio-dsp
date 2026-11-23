$ErrorActionPreference='Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
python -m pytest -q verification/model/tests/test_fixed_point.py verification/system/tests/test_serial_protocol.py verification/system/tests/test_synthetic_maritime.py
if ($LASTEXITCODE -ne 0) { throw 'software regression failed' }
python host/stabilize_video.py --out build/maritime_demo
if ($LASTEXITCODE -ne 0) { throw 'software maritime preview failed' }
Write-Host 'SOFTWARE_MARITIME_PREVIEW_PASS (not hardware evidence)'

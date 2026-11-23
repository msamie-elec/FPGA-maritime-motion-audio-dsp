# Host-only engineering analysis; NOT XSim, implementation or physical FPGA.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
& python .\verification\model\industrial_filter_assessment.py
if ($LASTEXITCODE -ne 0) {throw 'Filter coefficient/model assessment FAILED'}
& python -m pytest -q .\verification\model\tests\test_engineering_assessment.py .\verification\model\tests\test_fixed_point.py .\verification\model\tests\test_audio_fir_v09.py .\verification\system\tests\test_release_validation_tools.py
if ($LASTEXITCODE -ne 0) {throw 'Engineering Python regression FAILED'}
& python .\host\engineering_summary.py
if ($LASTEXITCODE -ne 0) {throw 'Summary report export FAILED'}
Write-Host 'ENGINEERING_REFERENCE_ASSESSMENT_COMPLETE; HDL and real FPGA require independent testing'

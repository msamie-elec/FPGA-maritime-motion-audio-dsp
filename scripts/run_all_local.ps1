# Single-command local development test. Board hardware still needs a COM-port test.
param(
  [string]$VivadoBin = 'C:\AMDDesignTools\2025.2.1\Vivado\bin',
  [switch]$SkipBitstream
)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not (Test-Path (Join-Path $VivadoBin 'vivado.bat'))) {
    throw "Vivado not found at $VivadoBin. Use -VivadoBin 'C:\your_path\Vivado\bin'."
}
$env:PATH = "$VivadoBin;$env:PATH"
Write-Host '[1/4] Running Python numerical and protocol tests'
python -m pytest -q tests/test_fixed_point.py tests/test_serial_protocol.py tests/test_synthetic_maritime.py
if ($LASTEXITCODE -ne 0) { throw 'Python regression failed' }
Write-Host '[2/4] Running full Vivado XSim serial UART + FIR regression'
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_maritime_xsim.ps1
if ($LASTEXITCODE -ne 0) { throw 'XSim UART+FIR regression failed' }
Write-Host '[3/4] Generating SOFTWARE-ONLY maritime video preview'
python host/stabilize_video.py --out build/maritime_demo
if ($LASTEXITCODE -ne 0) { throw 'Video software reference failed' }
if (-not $SkipBitstream) {
    Write-Host '[4/4] Running Vivado synthesis, implementation, bitstream and reports'
    & (Join-Path $VivadoBin 'vivado.bat') -mode batch -source scripts/build_maritime_bitstream.tcl
    if ($LASTEXITCODE -ne 0) { throw 'Vivado implementation failed: examine build logs' }
} else {
    Write-Host '[4/4] FPGA synthesis/bitstream SKIPPED by command option'
}
Write-Host 'LOCAL_DEV_WORKFLOW_COMPLETE. Physical UART/FPGA validation is STILL required.'

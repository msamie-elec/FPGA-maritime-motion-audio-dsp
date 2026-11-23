# Run from any PowerShell location with Vivado XSim tools on PATH.
# xsim reads hardware/sim/vectors/* relative to the repository root.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '../../..'))
python host/design_coefficients.py
if ($LASTEXITCODE -ne 0) { throw 'Coefficient generation failed' }
python host/generate_vectors.py
if ($LASTEXITCODE -ne 0) { throw 'Vector generation failed' }
python -m pytest -q verification/model/tests/test_fixed_point.py
if ($LASTEXITCODE -ne 0) { throw 'Python reference tests failed' }
foreach ($cmd in @('xvlog','xelab','xsim')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd is not on PATH; launch a Vivado-enabled shell." }
}
& xvlog -sv -i hardware/rtl hardware/rtl/fir_sequential.sv hardware/sim/tb/tb_fir_sequential.sv
if ($LASTEXITCODE -ne 0) { throw 'xvlog compilation failed' }
& xelab tb_fir_sequential -s maritime_fir_m1_snapshot
if ($LASTEXITCODE -ne 0) { throw 'xelab elaboration failed' }
& xsim maritime_fir_m1_snapshot -runall
if ($LASTEXITCODE -ne 0) { throw 'xsim simulation failed' }

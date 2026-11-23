$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../../.."))
python host/design_coefficients.py
if ($LASTEXITCODE -ne 0) { throw "Coefficient generation failed" }
python host/generate_vectors.py
if ($LASTEXITCODE -ne 0) { throw "Vector generation failed" }
python -m pytest -q verification/model/tests/test_fixed_point.py
if ($LASTEXITCODE -ne 0) { throw "Python reference regression failed" }
if (-not (Get-Command iverilog -ErrorAction SilentlyContinue)) { throw "Icarus Verilog not installed or not in PATH. Run the equivalent Vivado xsim flow." }
if (-not (Get-Command vvp -ErrorAction SilentlyContinue)) { throw "vvp missing" }
New-Item -ItemType Directory -Force -Path hardware/build/sim_cli | Out-Null
& iverilog -g2012 -s tb_fir_sequential -Ihardware/rtl -o hardware/build/sim_cli/fir_tb.vvp hardware/rtl/fir_sequential.sv hardware/sim/tb/tb_fir_sequential.sv
if ($LASTEXITCODE -ne 0) { throw "RTL compilation failed" }
& vvp hardware/build/sim_cli/fir_tb.vvp
if ($LASTEXITCODE -ne 0) { throw "RTL simulation failed" }

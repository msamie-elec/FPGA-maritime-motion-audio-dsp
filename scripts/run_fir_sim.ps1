$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
python host/design_coefficients.py
if ($LASTEXITCODE -ne 0) { throw "Coefficient generation failed" }
python host/generate_vectors.py
if ($LASTEXITCODE -ne 0) { throw "Vector generation failed" }
python -m pytest -q tests/test_fixed_point.py
if ($LASTEXITCODE -ne 0) { throw "Python reference regression failed" }
if (-not (Get-Command iverilog -ErrorAction SilentlyContinue)) { throw "Icarus Verilog not installed or not in PATH. Run the equivalent Vivado xsim flow." }
if (-not (Get-Command vvp -ErrorAction SilentlyContinue)) { throw "vvp missing" }
New-Item -ItemType Directory -Force -Path build | Out-Null
& iverilog -g2012 -s tb_fir_sequential -Irtl -o build/fir_tb.vvp rtl/fir_sequential.sv tb/tb_fir_sequential.sv
if ($LASTEXITCODE -ne 0) { throw "RTL compilation failed" }
& vvp build/fir_tb.vvp
if ($LASTEXITCODE -ne 0) { throw "RTL simulation failed" }

#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
cd "$(dirname "$0")/.."
python3 host/design_coefficients.py > /dev/null
python3 host/generate_vectors.py
python3 -m pytest -q tests/test_fixed_point.py
if ! command -v iverilog >/dev/null || ! command -v vvp >/dev/null; then
  echo 'RTL SIMULATION NOT RUN: install Icarus Verilog (iverilog/vvp) or run in Vivado simulator.' >&2
  exit 2
fi
mkdir -p build
iverilog -g2012 -s tb_fir_sequential -Irtl -o build/fir_tb.vvp \
  rtl/fir_sequential.sv tb/tb_fir_sequential.sv
vvp build/fir_tb.vvp

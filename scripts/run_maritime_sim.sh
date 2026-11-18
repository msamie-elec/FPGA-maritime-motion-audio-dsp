#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
iverilog -g2012 -s tb_maritime_uart_top -Irtl -o build/maritime_uart_tb.vvp \
 rtl/reset_sync.sv rtl/uart_rx.sv rtl/uart_tx.sv rtl/sample_buffer.sv \
 rtl/uart_packet_rx.sv rtl/uart_packet_tx.sv rtl/fir_sequential.sv \
 rtl/fir_job_controller.sv rtl/arty_a7_maritime_top.sv tb/tb_maritime_uart_top.sv
vvp build/maritime_uart_tb.vvp

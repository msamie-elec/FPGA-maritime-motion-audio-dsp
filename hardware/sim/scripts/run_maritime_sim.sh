#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p hardware/build/sim_cli
iverilog -g2012 -s tb_maritime_uart_top -Ihardware/rtl -o hardware/build/sim_cli/maritime_uart_tb.vvp \
 hardware/rtl/reset_sync.sv hardware/rtl/uart_rx.sv hardware/rtl/uart_tx.sv hardware/rtl/sample_buffer.sv \
 hardware/rtl/uart_packet_rx.sv hardware/rtl/uart_packet_tx.sv hardware/rtl/fir_sequential.sv \
 hardware/rtl/fir_job_controller.sv hardware/rtl/arty_a7_maritime_top.sv hardware/sim/tb/tb_maritime_uart_top.sv
vvp hardware/build/sim_cli/maritime_uart_tb.vvp

iverilog -g2012 -s tb_reset_sync -Ihardware/rtl -o hardware/build/sim_cli/maritime_reset_tb.vvp \
 hardware/rtl/reset_sync.sv hardware/sim/tb/tb_reset_sync.sv
vvp hardware/build/sim_cli/maritime_reset_tb.vvp

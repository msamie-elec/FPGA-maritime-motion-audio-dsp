$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '../../..'))
$src = @('reset_sync.sv','uart_rx.sv','uart_tx.sv','sample_buffer.sv','uart_packet_rx.sv','uart_packet_tx.sv','fir_sequential.sv','fir_job_controller.sv','arty_a7_maritime_top.sv') | ForEach-Object { "hardware/rtl/$_" }
& xvlog -sv -i hardware/rtl @src hardware/sim/tb/tb_maritime_uart_top.sv
if ($LASTEXITCODE -ne 0) { throw 'xvlog failed' }
& xelab tb_maritime_uart_top -s maritime_board_tb_snapshot
if ($LASTEXITCODE -ne 0) { throw 'xelab failed' }
& xsim maritime_board_tb_snapshot -runall
if ($LASTEXITCODE -ne 0) { throw 'xsim failed' }
# Independent reset/CDC regression (separate top and snapshot).
& xvlog -sv hardware/rtl/reset_sync.sv hardware/sim/tb/tb_reset_sync.sv
if ($LASTEXITCODE -ne 0) { throw 'reset xvlog failed' }
& xelab tb_reset_sync -s maritime_reset_tb_snapshot
if ($LASTEXITCODE -ne 0) { throw 'reset xelab failed' }
& xsim maritime_reset_tb_snapshot -runall
if ($LASTEXITCODE -ne 0) { throw 'reset xsim failed' }

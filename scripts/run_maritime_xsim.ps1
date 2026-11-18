$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$src = @('reset_sync.sv','uart_rx.sv','uart_tx.sv','sample_buffer.sv','uart_packet_rx.sv','uart_packet_tx.sv','fir_sequential.sv','fir_job_controller.sv','arty_a7_maritime_top.sv') | ForEach-Object { "rtl/$_" }
& xvlog -sv -i rtl @src tb/tb_maritime_uart_top.sv
if ($LASTEXITCODE -ne 0) { throw 'xvlog failed' }
& xelab tb_maritime_uart_top -s maritime_board_tb_snapshot
if ($LASTEXITCODE -ne 0) { throw 'xelab failed' }
& xsim maritime_board_tb_snapshot -runall
if ($LASTEXITCODE -ne 0) { throw 'xsim failed' }

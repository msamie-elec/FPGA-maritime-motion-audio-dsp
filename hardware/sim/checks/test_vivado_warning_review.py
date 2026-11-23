"""Non-Vivado assertions: structural smoke tests, NOT a substitution for XSim."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_uart_framing_error_wired_and_documented():
    rx=(ROOT/'hardware/rtl/uart_packet_rx.sv').read_text()
    assert 'if(uart_frame_error)' in rx
    assert 'ST_FRAMING=5' in rx
    tb=(ROOT/'hardware/sim/tb/tb_maritime_uart_top.sv').read_text()
    assert 'send_bad_stop_byte' in tb and "recv_checked(8'h35,5,0,0)" in tb

def test_sign_correct_and_reset_is_synchronous_at_ram_controls():
    fir=(ROOT/'hardware/rtl/fir_sequential.sv').read_text()
    assert 'accumulator + signed_product_extended' in fir
    reset=(ROOT/'hardware/rtl/reset_sync.sv').read_text()
    assert "logic [2:0] stages = 3'b111;" in reset
    assert 'always_ff @(posedge clk)' in reset
    assert 'stages <= {stages[1:0], button_reset};' in reset
    assert 'assign rst = stages[2];' in reset
    assert 'SHREG_EXTRACT = "NO"' in reset
    # The previous correction failed because stages[2] still had an asynchronous SR pin.
    assert 'posedge button_reset' not in reset
    assert 'negedge button_reset' not in reset
    assert 'rst_synchronous' not in reset

def test_board_voltage_and_intentional_async_io_exceptions_are_explicit():
    xdc=(ROOT/'hardware/constraints/arty_a7_35_maritime.xdc').read_text()
    assert 'set_property CFGBVS VCCO' in xdc
    assert 'set_property CONFIG_VOLTAGE 3.3' in xdc
    assert 'set_false_path -from [get_ports {uart_rxd_in btn_reset}]' in xdc
    assert 'set_false_path -to [get_ports {uart_txd_out led[0] led[1] led[2] led[3]}]' in xdc

def test_report_importer_present():
    s=(ROOT/'hardware/vivado/export_open_vivado_reports.tcl').read_text()
    assert 'open_run impl_1' in s
    assert 'summarize_release_reports.py' in s

def test_reset_testbench_is_connected_to_both_vivado_flows():
    tb=(ROOT/'hardware/sim/tb/tb_reset_sync.sv').read_text()
    assert 'MARITIME_RESET_SYNC_REGRESSION_PASS' in tb
    assert 'Asynchronous reset assertion detected' in tb
    assert 'Short glitch changed reset' in tb
    assert 'tb_reset_sync.sv' in (ROOT/'hardware/sim/scripts/run_maritime_xsim.ps1').read_text()
    assert 'tb_reset_sync.sv' in (ROOT/'hardware/vivado/create_maritime_vivado.tcl').read_text()
    assert 'tb_reset_sync.sv' in (ROOT/'hardware/build/maritime_a7.xpr').read_text()
    utb=(ROOT/'hardware/sim/tb/tb_maritime_uart_top.sv').read_text()
    assert 'Reset failed to restore idle request/serial state' in utb

def test_release_script_blocks_on_actual_ramb_drc():
    s=(ROOT/'scripts/final_rebuild_and_reports.ps1').read_text()
    assert "'REQP-1840','CFGBVS-1'" in s
    assert 'RELEASE_DRC_BLOCKED' in s
    assert 'RELEASE_DRC_SAFETY_GATE_PASS' in s

# Native Vivado reproducible project for board-level development.
set root [file normalize [file join [file dirname [info script]] ..]]
set dir [file join $root build vivado_maritime_a7]
create_project -force maritime_a7 $dir -part xc7a35ticsg324-1L
set_property target_language Verilog [current_project]
set sources [list reset_sync.sv uart_rx.sv uart_tx.sv sample_buffer.sv uart_packet_rx.sv uart_packet_tx.sv fir_sequential.sv fir_job_controller.sv arty_a7_maritime_top.sv]
foreach filename $sources {
  set path [file join $root rtl $filename]
  add_files $path
  set_property file_type SystemVerilog [get_files $path]
}
set_property include_dirs [list [file join $root rtl]] [get_filesets sources_1]
set_property top arty_a7_maritime_top [get_filesets sources_1]
add_files -fileset constrs_1 [file join $root constraints arty_a7_35_maritime.xdc]
set tb [file join $root tb tb_maritime_uart_top.sv]
add_files -fileset sim_1 $tb
set_property file_type SystemVerilog [get_files $tb]
set_property include_dirs [list [file join $root rtl]] [get_filesets sim_1]
set_property top tb_maritime_uart_top [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "MARITIME_VIVADO_PROJECT_READY: [file join $dir maritime_a7.xpr]"

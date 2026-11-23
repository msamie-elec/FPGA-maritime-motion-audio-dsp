# M1 RTL inspection project only; NOT a board-programmable top or bitstream.
# Usage (at repo root): vivado -mode batch -source hardware/vivado/create_fir_m1_vivado.tcl
set root [file normalize [file join [file dirname [info script]] .. ..]]
set project_dir [file join $root hardware build fir_m1_legacy]
create_project -force maritime_fir_m1 $project_dir -part xc7a35ticsg324-1L
set_property target_language Verilog [current_project]
set rtl_file [file join $root hardware rtl fir_sequential.sv]
add_files $rtl_file
set_property file_type SystemVerilog [get_files $rtl_file]
set_property include_dirs [list [file join $root hardware rtl]] [get_filesets sources_1]
set_property top fir_sequential [get_filesets sources_1]
set tb_file [file join $root hardware sim tb tb_fir_sequential.sv]
add_files -fileset sim_1 $tb_file
set_property file_type SystemVerilog [get_files $tb_file]
set_property include_dirs [list [file join $root hardware rtl]] [get_filesets sim_1]
set_property top tb_fir_sequential [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "M1 source-inspection project: [file join $project_dir maritime_fir_m1.xpr]"
puts "NOTICE: no board pins, UART, timing closure or hardware bitstream at M1."
puts "For standalone self-checking simulation, use hardware/sim/scripts/run_fir_xsim.ps1 from repository root."

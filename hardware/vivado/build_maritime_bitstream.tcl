# Board-level synthesis + routed implementation; run on local Vivado 2025.2.1.
# Creates the project afresh to avoid stale local GUI state.
set root [file normalize [file join [file dirname [info script]] .. ..]]
source [file join $root hardware vivado create_maritime_vivado.tcl]
set reports [file join $root hardware build reports]
file mkdir $reports
launch_runs synth_1 -jobs 4
wait_on_run synth_1
set st [get_property STATUS [get_runs synth_1]]
puts "SYNTH_STATUS $st"
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed: $st"}
open_run synth_1
report_utilization -file [file join $reports utilization_synth.rpt]
close_design
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
set st [get_property STATUS [get_runs impl_1]]
puts "IMPL_STATUS $st"
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed: $st"}
open_run impl_1
report_utilization -file [file join $reports utilization_routed.rpt]
report_timing_summary -report_unconstrained -file [file join $reports timing_routed.rpt]
report_drc -file [file join $reports drc_routed.rpt]
puts "MARITIME_BOARD_BITSTREAM_BUILD_COMPLETE: [file join $root hardware build maritime_a7.runs impl_1 arty_a7_maritime_top.bit]"
puts "NOTICE: Actual physical hardware correctness remains to be tested on Arty A7."

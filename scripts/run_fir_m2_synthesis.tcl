# M2: FIR-core-only synthesis and preliminary resource/timing estimates.
# Prerequisite: scripts/create_fir_m1_vivado.tcl already created the .xpr.
# Run while the Vivado GUI is CLOSED to avoid two sessions writing same project.
# Usage from repository root:
#   vivado -mode batch -source scripts/run_fir_m2_synthesis.tcl
set root [file normalize [file join [file dirname [info script]] ..]]
set proj [file join $root build vivado_fir_m1 maritime_fir_m1.xpr]
set xdc [file join $root constraints fir_m2_clock_only.xdc]
set reports [file join $root build vivado_fir_m1 reports_m2]
if {![file exists $proj]} {
    error "M1 Vivado project does not exist: $proj. First run scripts/create_fir_m1_vivado.tcl."
}
if {![file exists $xdc]} { error "Clock constraint file missing: $xdc" }
file mkdir $reports
open_project $proj
set_property top fir_sequential [get_filesets sources_1]
set previous [get_files -quiet $xdc]
if {[llength $previous] == 0} {
    add_files -fileset constrs_1 $xdc
}
update_compile_order -fileset sources_1

# Reset only the synthesis run to ensure source/constraint edits are included.
reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
set progress [get_property PROGRESS [get_runs synth_1]]
set status [get_property STATUS [get_runs synth_1]]
puts "M2_SYNTH_STATUS: $status; progress=$progress"
if {$progress ne "100%"} {
    error "M2 synthesis did not complete: $status"
}
open_run synth_1
report_utilization -hierarchical -file [file join $reports fir_utilization_post_synth.rpt]
report_timing_summary -report_unconstrained -file [file join $reports fir_timing_post_synth.rpt]
write_checkpoint -force [file join $reports fir_post_synth.dcp]
puts "M2_FIR_SYNTHESIS_REPORTS_READY: $reports"
puts "NOTICE: These are post-synthesis (not routed) estimates. The FIR-only module"
puts "has no package pin constraints or board-level UART. Do NOT generate a bitstream"
puts "or claim physical timing closure until the complete board top is implemented."
close_project

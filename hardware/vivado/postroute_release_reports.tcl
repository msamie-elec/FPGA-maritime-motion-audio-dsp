# Run from Vivado 2025.2.1: vivado -mode batch -source hardware/vivado/postroute_release_reports.tcl
# Reads a completed implementation; it does NOT rerun or change routing.
set root [file normalize [file join [file dirname [info script]] .. ..]]
set project [file join $root hardware build maritime_a7.xpr]
if {![file exists $project]} {error "Missing Vivado project; run unified build first: $project"}
open_project $project
set impl [get_runs impl_1]
if {[get_property PROGRESS $impl] ne "100%"} {error "impl_1 is not complete; do not report power on an incomplete route"}
open_run impl_1
set out [file join $root hardware build reports]
file mkdir $out
report_timing_summary -report_unconstrained -file [file join $out timing_routed_final.rpt]
report_utilization -file [file join $out utilization_routed_final.rpt]
report_drc -file [file join $out drc_routed_final.rpt]
report_methodology -file [file join $out methodology_routed.rpt]
report_clock_interaction -file [file join $out clock_interaction_routed.rpt]
# Vectorless estimate, using defaults where switching activity is unknown.
# NEVER call this measured board power or characterize cold/hot power with it.
report_power -file [file join $out power_routed_vectorless.rpt]
set manifest [open [file join $out power_assumptions.txt] w]
puts $manifest "Power is post-route VIVADO ESTIMATE using default vectorless switching on unspecified nets."
puts $manifest "Not board input power; not actual workload toggling; not temperature-chamber measurement."
puts $manifest "For improved estimates, provide realistic simulation SAIF/activity and environmental conditions."
puts $manifest "Use XADC for silicon die temperature only; it does not measure total board watts."
close $manifest
puts "FINAL_POSTROUTE_REPORTS_COMPLETE $out"
close_project

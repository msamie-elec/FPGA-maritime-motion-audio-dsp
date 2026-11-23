# Executed in the Vivado GUI Tcl Console AFTER implementation is complete.
# Captures the currently open native .xpr run and generates fresh GUI Summary
# Report data (NOT merely a copy of the earlier Nov 20 archive).
set root [file normalize [file join [file dirname [info script]] .. ..]]
if {[catch {current_project} project] || $project eq ""} {error "Open the maritime_a7 Vivado project first"}
set run [get_runs impl_1]
if {[llength $run] != 1} {error "No impl_1 found in current project"}
if {[get_property PROGRESS $run] ne "100%"} {error "impl_1 is not complete: route/build first"}
open_run impl_1
set stamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
set out [file join $root evidence final_validation build_$stamp]
file mkdir $out
report_timing_summary -report_unconstrained -file [file join $out timing_routed_final.rpt]
report_utilization -file [file join $out utilization_routed_final.rpt]
report_drc -file [file join $out drc_routed_final.rpt]
report_methodology -file [file join $out methodology_routed.rpt]
report_clock_interaction -file [file join $out clock_interaction_routed.rpt]
report_power -file [file join $out power_routed_vectorless.rpt]
set f [open [file join $out power_assumptions.txt] w]
puts $f "Vectorless Vivado estimate, NOT board power or workload-measured power."
close $f
# Python must be available, as for the installed host GUI.
if {[catch {exec python [file join $root scripts summarize_release_reports.py] --report-dir $out --json [file join $out report_summary.json] --markdown [file join $out report_summary.md]} e]} {
  puts "WARNING: Vivado reports captured, but Python parser did not run: $e"
  puts "Run scripts/summarize_release_reports.py manually, then refresh GUI summary."
} else {
  puts "MARITIME_GUI_SUMMARY_READY: [file join $out report_summary.json]"
}
puts "MARITIME_NATIVE_GUI_REPORTS_EXPORTED: $out"

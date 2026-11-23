# Run INSIDE Vivado Hardware Manager Tcl Console, after Open Target/Auto Connect.
# Usage: source hardware/vivado/sample_xadc_snapshot.tcl
# Override phase in Tcl console before source: set ::env(MARITIME_PHASE) cold
set root [file normalize [file join [file dirname [info script]] .. ..]]
set dir [file join $root evidence final_validation]
file mkdir $dir
set path [file join $dir xadc_snapshots.csv]
set phase "unspecified"
if {[info exists ::env(MARITIME_PHASE)]} {set phase $::env(MARITIME_PHASE)}
set mons [get_hw_sysmons]
if {[llength $mons] < 1} {error "No XADC/System Monitor available: connect to programmed Arty A7 in Hardware Manager"}
set mon [lindex $mons 0]
refresh_hw_sysmon -properties {TEMPERATURE} $mon
set val [get_property TEMPERATURE $mon]
if {$val eq ""} {error "XADC TEMPERATURE property empty; no measurement recorded"}
set newfile [expr {![file exists $path]}]
set fd [open $path a]
if {$newfile} {puts $fd "timestamp_local,phase,die_temperature_c,source"}
puts $fd "[clock format [clock seconds] -format {%Y-%m-%dT%H:%M:%S%z}],$phase,$val,Vivado_Hardware_Manager_XADC"
close $fd
puts "XADC_SNAPSHOT $phase die_temperature_c=$val csv=$path"

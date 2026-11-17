# FIR core-only 100 MHz clock constraint for synthesis exploration.
# Not an Arty A7 board XDC: deliberately no package pin assignments.
# Valid only when fir_sequential is the top module.
create_clock -name fir_clk -period 10.000 [get_ports clk]

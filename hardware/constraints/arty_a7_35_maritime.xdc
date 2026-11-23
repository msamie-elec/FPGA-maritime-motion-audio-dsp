# Original pin assignments from Digilent Arty-A7-35-Master.xdc.
# https://github.com/Digilent/digilent-xdc/blob/master/Arty-A7-35-Master.xdc
set_property -dict { PACKAGE_PIN E3 IOSTANDARD LVCMOS33 } [get_ports {CLK100MHZ}]
create_clock -name sys_clk_pin -period 10.000 -waveform {0 5} [get_ports {CLK100MHZ}]
set_property -dict { PACKAGE_PIN A9 IOSTANDARD LVCMOS33 } [get_ports {uart_rxd_in}]
set_property -dict { PACKAGE_PIN D10 IOSTANDARD LVCMOS33 } [get_ports {uart_txd_out}]
set_property -dict { PACKAGE_PIN D9 IOSTANDARD LVCMOS33 } [get_ports {btn_reset}]
set_property -dict { PACKAGE_PIN H5 IOSTANDARD LVCMOS33 } [get_ports {led[0]}]
set_property -dict { PACKAGE_PIN J5 IOSTANDARD LVCMOS33 } [get_ports {led[1]}]
set_property -dict { PACKAGE_PIN T9 IOSTANDARD LVCMOS33 } [get_ports {led[2]}]
set_property -dict { PACKAGE_PIN T10 IOSTANDARD LVCMOS33 } [get_ports {led[3]}]

# Arty A7 configuration voltage: 3.3 V configuration-bank interface with
# CFGBVS tied to VCCO (verify board revision and electrical schematic before re-targeting).
# AMD UG899/UG912; Arty reference design examples and Avnet Arty SREC guide.
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

# Board USB-UART is asynchronous to CLK100MHZ (115200 8N1, oversampled through
# rx_meta/rx_sync). Button reset is an asynchronous human input, with internal
# synchronization. These are deliberate async-domain exceptions, NOT virtual
# zero-delay synchronous input assumptions.
set_false_path -from [get_ports {uart_rxd_in btn_reset}]
# No source-synchronous timing relationship exists to the external USB-UART
# receiver or indicator LEDs. The bit period and functional operation must be
# verified by serial line simulation and physical tests, not by a 100 MHz
# I/O output setup analysis with fabricated output-delay budgets.
set_false_path -to [get_ports {uart_txd_out led[0] led[1] led[2] led[3]}]

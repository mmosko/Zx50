# Master Clock constraint (approx 30 MHz)
create_clock -name mclk -period 33.333 [get_ports {mclk}]

# Z80 Clock constraint (approx 7.5 MHz, derived as MCLK / 4)
create_clock -name zclk -period 133.332 [get_ports {zclk}]

# Tell Quartus that these two clocks are completely asynchronous to each other
# (Since the Z80 clock can be stepped manually or halted by the PIC)
set_clock_groups -asynchronous -group {mclk} -group {zclk}

sudo openocd -c "adapter driver ch347" \
  -c "ch347 vid_pid 0x1a86 0x55dd" \
  -c "adapter speed 1000" \
  -c "jtag newtap atf1508 tap -irlen 10 -expected-id 0x0150803f" \
  -c "init" \
  -c "svf zx50_cpld_core.svf" \
  -c "shutdown"


all:
	iverilog -o wait_gen_sim wait_gen.v wait_gen_tb.v
	vvp wait_gen_sim
	#surfer wait_gen.vcd

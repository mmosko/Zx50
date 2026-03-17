.PHONY: run-% view-%

# Variables
VERILOG_COMPILER = iverilog
SIM_RUNTIME      = vvp
VIEWER           = gtkwave

# Directories
SRC_DIR   = ./src
SIM_DIR   = ./sim
OUT_DIR   = ./build
GTK_DIR   = ./gtkw
WAVES_DIR = waves


# Dynamically find every testbench
TESTBENCHES := $(wildcard $(SIM_DIR)/*_tb.v)

# Transform the strings from "sim/module_name_tb.v" into "run-module_name"
RUN_TARGETS := $(patsubst $(SIM_DIR)/%_tb.v,run-%,$(TESTBENCHES))

all: $(RUN_TARGETS)

# Ensure directories exist
$(shell mkdir -p $(SIM_DIR) $(WAVES_DIR) $(OUT_DIR))

# Pattern Rule: Compiles any sim/%.vvp using src/ as an auto-discovery library

$(OUT_DIR)/%.vvp: $(SIM_DIR)/%_tb.v $(wildcard $(SRC_DIR)/*.v)
	@mkdir -p $(OUT_DIR)
	# $< is the testbench. -y tells it where to find missing modules.
	$(VERILOG_COMPILER) -y $(SRC_DIR) -o $@ $<

# 2. Pattern Rule: Runs the simulation and generates the VCD
$(WAVES_DIR)/%.vcd: $(OUT_DIR)/%.vvp
	@mkdir -p $(WAVES_DIR)
	$(SIM_RUNTIME) $<

# --- High-Level Commands ---


run-%: $(SIM_DIR)/%_tb.v $(wildcard $(SRC_DIR)/*.v)
	@echo "\n--- Compiling $* ---"
	$(VERILOG_COMPILER) -y $(SRC_DIR) -o $(OUT_DIR)/$*.vvp $<
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/$*.vvp
	@echo "--- Simulation Complete. Waves saved to $(WAVES_DIR)/$*.vcd ---"
	@touch $(GTK_DIR)/$*.gtkw
	@echo "--- Finished Test---\n"

# Helper to view a specific wave (e.g., 'make view-zx50_mmu_sram')
view-%: $(WAVES_DIR)/%.vcd $(GTK_DIR)/%.gtkw
	$(VIEWER) $^

clean:
	rm -rf $(OUT_DIR)/*.vvp $(WAVES_DIR)/*.vcd 

# ==============================================================================
# Yosys Dry-Run (MacBook / Local Troubleshooting)
# ==============================================================================
# This target runs the exact Atmel synthesis flow without invoking the legacy fitter.
# It is perfect for checking Verilog syntax, linting, and logic mapping on ARM/Mac.
#
# Expects atf1508 library in project parent
# git clone  https://github.com/hoglet67/atf15xx_yosys.git
# Path to the Atmel Yosys libraries
ATF_DIR = ../../atf15xx_yosys

yosys-check: $(CPLD_SRC)
	@echo "\n--- Running Yosys Atmel Synthesis Check ---"
	@mkdir -p $(OUT_DIR)
	# Runs the identical sequence to run_yosys.sh but outputs a JSON netlist for local viewing
	yosys -p " \
		read_liberty -lib $(ATF_DIR)/cells.lib; \
		read_verilog $(CPLD_SRC); \
		tribuf; \
		synth -flatten -noabc -top $(TOP_MODULE); \
		techmap -map $(ATF_DIR)/techmap.v -D skip_DFFE_XX_; \
		simplemap; \
		dfflibmap -liberty $(ATF_DIR)/cells.lib; \
		abc -liberty $(ATF_DIR)/cells.lib; \
		iopadmap -bits -inpad INBUF Q:A -outpad BUF A:Q -toutpad TRI ENA:A:Q -tinoutpad bibuf EN:Q:A:PAD; \
		clean; \
		hierarchy -check -top $(TOP_MODULE); \
		splitnets -format _; \
		rename -wire -suffix _reg t:*DFF*; \
		rename -wire -suffix _comb; \
		write_json $(OUT_DIR)/$(TOP_MODULE)_dryrun.json"
	@echo "--- Yosys Synthesis Check Complete! No errors found. ---\n"

# ==============================================================================
# Synthesis & Flashing (ATF1508AS via Yosys & OpenOCD)
# ==============================================================================
# Define your pure CPLD source files here (Exclude simulation BFMs!)
CPLD_SRC = $(SRC_DIR)/zx50_cpld_core.v \
           $(SRC_DIR)/zx50_bus_arbiter.v \
           $(SRC_DIR)/zx50_dma.v \
           $(SRC_DIR)/zx50_mmu_sram.v

TOP_MODULE = zx50_cpld_core
DEVICE     = ATF1508AS-100-TQFP

# Paths to your cloned tools (Update these to match where you cloned them)
ATF_FITTER = ~/git/atf15xx_yosys/yosys-atf15xx
JED2SVF    = python3 ~/git/prjbureau/util/fuseconf.py

syn: $(CPLD_SRC)
	@echo "\n--- 1. Yosys Synthesis & Atmel Fitter ---"
	@mkdir -p $(OUT_DIR)
	# This script runs Yosys, generates the EDIF, and calls Wine/fit1508.exe
	$(ATF_FITTER) -d $(DEVICE) -t $(TOP_MODULE) $(CPLD_SRC) -o $(OUT_DIR)/$(TOP_MODULE).jed

	@echo "--- 2. Converting JED to SVF ---"
	$(JED2SVF) $(OUT_DIR)/$(TOP_MODULE).jed $(OUT_DIR)/$(TOP_MODULE).svf
	@echo "--- Synthesis Complete! SVF ready for flashing. ---\n"

flash: $(OUT_DIR)/$(TOP_MODULE).svf
	@echo "\n--- Flashing CPLD via Waveshare CH347 & OpenOCD ---"
	# Connects via CH347, defines the JTAG TAP for the ATF1508, and pushes the SVF
	openocd -f interface/ch347.cfg \
	        -c "adapter speed 1000" \
	        -c "jtag newtap atf1508 tap -irlen 3 -expected-id 0x0150803f" \
	        -c "init; svf $(OUT_DIR)/$(TOP_MODULE).svf; exit"

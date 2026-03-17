.PHONY: run-% view-% syn

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
	rm -rf $(OUT_DIR)/*.vvp $(WAVES_DIR)/*.vcd $(SYN_DIR)/*

# ==============================================================================
# Global CPLD Variables
# ==============================================================================
SYN_DIR    = ./syn
TOP_MODULE = zx50_cpld_core
DEVICE     = ATF1508AS
PACKAGE    = TQFP100

# Define pure CPLD source files (Exclude simulation BFMs!)
CPLD_SRC = zx50_cpld_core.v zx50_bus_arbiter.v zx50_dma.v zx50_mmu_sram.v

# Centralized array with full paths to avoid scattered addprefix commands
CPLD_FILES = $(addprefix $(SRC_DIR)/, $(CPLD_SRC))

# Tool Paths
ATF_DIR    = ../../atf15xx_yosys
ATF_YOSYS  = ~/git/atf15xx_yosys/run_yosys.sh
ATF_FITTER = ~/git/atf15xx_yosys/run_fitter.sh
JED2SVF    = python3 ~/git/prjbureau/util/fuseconf.py

# ==============================================================================
# Yosys Dry-Run (MacBook / Local Troubleshooting)
# ==============================================================================
# Runs the exact Atmel synthesis flow without invoking the legacy Wine fitter.
yosys-check: $(CPLD_FILES)
	@echo "\n--- Running Yosys Atmel Synthesis Check ---"
	@mkdir -p $(SYN_DIR)
	yosys -q -l $(SYN_DIR)/yosys_check.log -p " \
		read_liberty -lib $(ATF_DIR)/cells.lib; \
		read_verilog $(CPLD_FILES); \
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
		stat; \
		write_json $(SYN_DIR)/$(TOP_MODULE)_dryrun.json"
	
	@echo "--- Yosys Synthesis Check Complete! No errors found. ---"
	@echo "Log saved to: $(SYN_DIR)/yosys_check.log"
	@grep -A 25 "=== $(TOP_MODULE) ===" $(SYN_DIR)/yosys_check.log || true
	@echo "\n"

# ==============================================================================
# Synthesis & Flashing (ATF1508AS via Yosys & OpenOCD)
# ==============================================================================
syn: $(CPLD_FILES)
	@echo "\n--- 1. Yosys Synthesis & Atmel Fitter ---"
	@mkdir -p $(SYN_DIR)
	
	# Symlink all source files into syn/ so legacy tools can find them locally
	@for file in $(CPLD_SRC); do \
		ln -sf ../$(SRC_DIR)/$$file $(SYN_DIR)/$$file; \
	done
	
	# Execute Yosys from within syn/ to capture the EDIF and logs cleanly
	# We use abspath to ensure the shell script finds the files regardless of the cd
	cd $(SYN_DIR) && $(ATF_YOSYS) $(TOP_MODULE) $(abspath $(CPLD_FILES))
	
	# Execute the Atmel Fitter from within syn/ to capture the JED, FIT, and TT2 files
	cd $(SYN_DIR) && $(ATF_FITTER) -d $(DEVICE) -p $(PACKAGE) -t $(TOP_MODULE)

	@echo "\n--- 2. Converting JED to SVF ---"
	$(JED2SVF) $(SYN_DIR)/$(TOP_MODULE).jed $(SYN_DIR)/$(TOP_MODULE).svf
	@echo "--- Synthesis Complete! SVF ready for flashing. ---\n"

flash: $(SYN_DIR)/$(TOP_MODULE).svf
	@echo "\n--- Flashing CPLD via Waveshare CH347 & OpenOCD ---"
	openocd -f interface/ch347.cfg \
	        -c "adapter speed 1000" \
	        -c "jtag newtap atf1508 tap -irlen 3 -expected-id 0x0150803f" \
	        -c "init; svf $(SYN_DIR)/$(TOP_MODULE).svf; exit"
	@echo "--- Flashing Complete! ---\n"

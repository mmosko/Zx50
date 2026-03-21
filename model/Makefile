.PHONY: run-% view-% syn

FLAGS = -DHW_REV_A11_BUG

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
	$(VERILOG_COMPILER) $(FLAGS) -y $(SRC_DIR) -o $(OUT_DIR)/$*.vvp $<
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/$*.vvp
	@echo "--- Simulation Complete. Waves saved to $(WAVES_DIR)/$*.vcd ---"
	@touch $(GTK_DIR)/$*.gtkw
	@echo "--- Finished Test---\n"

# Helper to view a specific wave (e.g., 'make view-zx50_mmu_sram')
view-%: $(WAVES_DIR)/%.vcd $(GTK_DIR)/%.gtkw
	$(VIEWER) $^

# ==============================================================================
# Cleanup Targets
# ==============================================================================

clean:
	@echo "--- Cleaning simulation and intermediate synthesis artifacts ---"
	rm -rf $(OUT_DIR)/*.vvp $(WAVES_DIR)/*.vcd
	@if [ -d $(SYN_DIR) ]; then \
		echo "Cleaning $(SYN_DIR) (preserving .svf, .fit, and .gitkeep)..."; \
		find $(SYN_DIR) -type f ! -name '*.svf' ! -name '*.fit' ! -name '.gitkeep' -delete; \
		find $(SYN_DIR) -type l -delete; \
	fi

realclean: clean
	@echo "--- Deep clean: Removing ALL synthesis outputs including .svf and .fit ---"
	@if [ -d $(SYN_DIR) ]; then \
		find $(SYN_DIR) -type f ! -name '.gitkeep' -delete; \
		find $(SYN_DIR) -type l -delete; \
	fi
	rm -rf $(OUT_DIR)/*
	rm -rf $(WAVES_DIR)/*

# ==============================================================================
# Yosys Dry-Run (MacBook / Local Troubleshooting)
# ==============================================================================
# Runs the exact Atmel synthesis flow without invoking the legacy Wine fitter.

# Master Target: Run both dry-runs
#yosys-check: yosys-check_dma yosys-check_nodma
yosys-check: yosys-check_dma

yosys-check_dma: $(DMA_FILES)
	@echo "\n--- Running Yosys Atmel Synthesis Check (WITH DMA) ---"
	@mkdir -p $(SYN_DIR)
	yosys -q -l $(SYN_DIR)/yosys_check_dma.log -p " \
		read_liberty -lib $(ATF_DIR)/cells.lib; \
		read_verilog $(DMA_FILES); \
		tribuf; \
		synth -flatten -noabc -top $(DMA_TOP); \
		techmap -map $(ATF_DIR)/techmap.v -D skip_DFFE_XX_; \
		simplemap; \
		dfflibmap -liberty $(ATF_DIR)/cells.lib; \
		abc -liberty $(ATF_DIR)/cells.lib; \
		iopadmap -bits -inpad INBUF Q:A -outpad BUF A:Q -toutpad TRI EN:A:Q -tinoutpad bibuf EN:Q:A:PAD; \
		clean; \
		hierarchy -check -top $(DMA_TOP); \
		splitnets -format _; \
		rename -wire -suffix _reg t:*DFF*; \
		rename -wire -suffix _comb; \
		stat; \
		write_json $(SYN_DIR)/$(DMA_TOP)_dryrun.json"
	
	@echo "--- DMA Synthesis Check Complete! No errors found. ---"
	@echo "Log saved to: $(SYN_DIR)/yosys_check_dma.log"
	@grep -A 25 "=== $(DMA_TOP) ===" $(SYN_DIR)/yosys_check_dma.log || true
	@echo "\n"

yosys-check_nodma: $(NODMA_FILES)
	@echo "\n--- Running Yosys Atmel Synthesis Check (NoDMA Fallback) ---"
	@mkdir -p $(SYN_DIR)
	yosys -q -l $(SYN_DIR)/yosys_check_nodma.log -p " \
		read_liberty -lib $(ATF_DIR)/cells.lib; \
		read_verilog $(NODMA_FILES); \
		tribuf; \
		synth -flatten -noabc -top $(NODMA_TOP); \
		techmap -map $(ATF_DIR)/techmap.v -D skip_DFFE_XX_; \
		simplemap; \
		dfflibmap -liberty $(ATF_DIR)/cells.lib; \
		abc -liberty $(ATF_DIR)/cells.lib; \
		iopadmap -bits -inpad INBUF Q:A -outpad BUF A:Q -toutpad TRI EN:A:Q -tinoutpad bibuf EN:Q:A:PAD; \
		clean; \
		hierarchy -check -top $(NODMA_TOP); \
		splitnets -format _; \
		rename -wire -suffix _reg t:*DFF*; \
		rename -wire -suffix _comb; \
		stat; \
		write_json $(SYN_DIR)/$(NODMA_TOP)_dryrun.json"
	
	@echo "--- NoDMA Synthesis Check Complete! No errors found. ---"
	@echo "Log saved to: $(SYN_DIR)/yosys_check_nodma.log"
	@grep -A 25 "=== $(NODMA_TOP) ===" $(SYN_DIR)/yosys_check_nodma.log || true
	@echo "\n"

# ==============================================================================
# Global CPLD Variables & Paths
# ==============================================================================
SYN_DIR    = ./syn
DEVICE     = ATF1508AS
PACKAGE    = TQFP100

# Tool Paths
ATF_DIR    = ../../atf15xx_yosys
ATF_YOSYS  = ~/git/atf15xx_yosys/run_yosys.sh
ATF_FITTER = ~/git/atf15xx_yosys/run_fitter.sh
JED2SVF    = PYTHONPATH=~/git/prjbureau python3 -m util.fuseconv --device $(DEVICE)

# --- DMA Config ---
DMA_TOP    = zx50_cpld_core
DMA_SRC    = zx50_cpld_core.v zx50_bus_arbiter.v zx50_dma.v zx50_mmu_sram.v
DMA_FILES  = $(addprefix $(SRC_DIR)/, $(DMA_SRC))

# --- NoDMA Config ---
NODMA_TOP  = zx50_cpld_nodma
NODMA_SRC  = zx50_cpld_nodma.v zx50_mmu_sram.v
NODMA_FILES = $(addprefix $(SRC_DIR)/, $(NODMA_SRC))

# ==============================================================================
# Synthesis & Flashing (ATF1508AS via Yosys & OpenOCD)
# ==============================================================================

# Master target: Build both!
#syn: syn_dma syn_nodma
syn: syn_dma 

syn_dma: $(DMA_FILES)
	@echo "\n--- 1. Yosys Synthesis & Atmel Fitter (WITH DMA) ---"
	@mkdir -p $(SYN_DIR)
	@for file in $(DMA_SRC); do \
		ln -sf ../$(SRC_DIR)/$$file $(SYN_DIR)/$$file; \
	done
	
	cd $(SYN_DIR) && $(ATF_YOSYS) $(DMA_TOP) $(DMA_SRC)
	cd $(SYN_DIR) && $(ATF_FITTER) -d $(DEVICE) -p $(PACKAGE) -t $(DMA_TOP)

	@echo "\n--- 2. Converting JED to SVF ---"
	$(JED2SVF) $(SYN_DIR)/$(DMA_TOP).jed $(SYN_DIR)/$(DMA_TOP).svf
	@echo "--- DMA Synthesis Attempt Complete! ---\n"

syn_nodma: $(NODMA_FILES)
	@echo "\n--- 1. Yosys Synthesis & Atmel Fitter (NoDMA Fallback) ---"
	@mkdir -p $(SYN_DIR)
	@for file in $(NODMA_SRC); do \
		ln -sf ../$(SRC_DIR)/$$file $(SYN_DIR)/$$file; \
	done
	
	cd $(SYN_DIR) && $(ATF_YOSYS) $(NODMA_TOP) $(NODMA_SRC)
	cd $(SYN_DIR) && $(ATF_FITTER) -d $(DEVICE) -p $(PACKAGE) -t $(NODMA_TOP)

	@echo "\n--- 2. Converting JED to SVF ---"
	$(JED2SVF) $(SYN_DIR)/$(NODMA_TOP).jed $(SYN_DIR)/$(NODMA_TOP).svf
	@echo "--- NoDMA Synthesis Complete! SVF ready for flashing. ---\n"

# ==============================================================================
# Flashing Targets
# ==============================================================================

flash_dma: $(SYN_DIR)/$(DMA_TOP).svf
	@echo "\n--- Flashing FULL DMA CPLD via Waveshare CH347 & OpenOCD ---"
	openocd -f interface/ch347.cfg \
	        -c "adapter speed 1000" \
	        -c "jtag newtap atf1508 tap -irlen 3 -expected-id 0x0150803f" \
	        -c "init; svf $(SYN_DIR)/$(DMA_TOP).svf; exit"

flash_nodma: $(SYN_DIR)/$(NODMA_TOP).svf
	@echo "\n--- Flashing NoDMA CPLD via Waveshare CH347 & OpenOCD ---"
	openocd -f interface/ch347.cfg \
	        -c "adapter speed 1000" \
	        -c "jtag newtap atf1508 tap -irlen 3 -expected-id 0x0150803f" \
	        -c "init; svf $(SYN_DIR)/$(NODMA_TOP).svf; exit"

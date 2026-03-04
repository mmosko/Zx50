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

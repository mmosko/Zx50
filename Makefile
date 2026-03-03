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


all: run-zx50_mmu_sram run-zx50_conflict run-zx50_bus_arbiter \
	run-arbiter_exhaustive

# Ensure directories exist
$(shell mkdir -p $(SIM_DIR) $(WAVES_DIR) $(OUT_DIR))

# 1. Pattern Rule: Compiles any sim/%.vvp from src/%.v and sim/%_tb.v
# Example: 'make sim/zx50_mmu_sram.vvp' looks for src/zx50_mmu_sram.v and sim/zx50_mmu_sram_tb.v
$(OUT_DIR)/%.vvp: $(SRC_DIR)/%.v $(SIM_DIR)/%_tb.v
	@mkdir -p $(OUT_DIR)
	$(VERILOG_COMPILER) -o $@ $^

# 2. Pattern Rule: Runs the simulation and generates the VCD
$(WAVES_DIR)/%.vcd: $(OUT_DIR)/%.vvp
	@mkdir -p $(WAVES_DIR)
	$(SIM_RUNTIME) $<

# --- High-Level Commands ---

run-arbiter_exhaustive: $(SIM_DIR)/arbiter_exhaustive_tb.v $(SRC_DIR)/zx50_bus_arbiter.v
	@echo "\n--- Compiling Arbiter Test ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/arbiter_exhaustive_tb.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/arbiter_exhaustive_tb.vvp
	@touch $(GTK_DIR)/arbiter_exhaustive_tb.gtkw
	@echo "--- Finished Test ---\n"


run-zx50_conflict: $(SRC_DIR)/zx50_mmu_sram.v $(SIM_DIR)/zx50_conflict_tb.v
	@echo "\n--- Compiling Conflict Test (SRAM version) ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/zx50_conflict.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/zx50_conflict.vvp
	@touch $(GTK_DIR)/zx50_conflict.gtkw
	@echo "--- Finished Test---\n"

run-%: $(SRC_DIR)/*.v $(SIM_DIR)/%_tb.v
	@echo "\n--- Compiling $* ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/$*.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/$*.vvp
	@touch $(GTK_DIR)/$*.gtkw
	@echo "--- Finished Test---\n"

# Helper to view a specific wave (e.g., 'make view-zx50_mmu_sram')
view-%: $(WAVES_DIR)/%.vcd $(GTK_DIR)/%.gtkw
	$(VIEWER) $^

clean:
	rm -rf $(OUT_DIR)/*.vvp $(WAVES_DIR)/*.vcd 

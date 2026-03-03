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

run-arbiter_exhaustive: $(SIM_DIR)/arbiter_exhaustive_tb.v
	@echo "--- Compiling Arbiter Test ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/arbiter_exhaustive_tb.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/arbiter_exhaustive_tb.vvp
	@touch $(SIM_DIR)/arbiter_exhaustive_tb.gtkw


run-zx50_conflict: $(SRC_DIR)/zx50_mmu.v $(SIM_DIR)/zx50_conflict_tb.v
	@echo "--- Compiling Conflict Test (SRAM version) ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/zx50_conflict.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/zx50_conflict.vvp
	@touch $(SIM_DIR)/zx50_conflict.gtkw

run-%: $(SRC_DIR)/*.v $(SIM_DIR)/%_tb.v
	@echo "--- Compiling $* ---"
	$(VERILOG_COMPILER) -o $(OUT_DIR)/$*.vvp $^
	@echo "--- Running Simulation ---"
	$(SIM_RUNTIME) $(OUT_DIR)/$*.vvp
	@echo "--- Simulation Complete. Waves saved to $(WAVES_DIR)/$*.vcd ---"
	@touch $(GTK_DIR)/$*.gtkw

# Helper to view a specific wave (e.g., 'make view-zx50_mmu_sram')
view-%: $(WAVES_DIR)/%.vcd $(GTK_DIR)/%.gtkw
	$(VIEWER) $^

clean:
	rm -rf $(OUT_DIR)/*.vvp $(WAVES_DIR)/*.vcd 

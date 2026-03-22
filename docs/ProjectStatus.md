# ZX50 Project Checkpoint & State Save

*Last Updated: March 22, 2026*

## 🏆 Current Achievements & State

1. **Zx50 Bus Probe Host Software (Completed)**:
   * **SCPI Driver (`scope_control.py`)**: Successfully wrapped the Tektronix MDO3034 LAN interface. Resolved parsing errors by explicitly silencing header chatter (`HEADer OFF`) and eliminated artificial voltage dividers by forcing `CH1` and `CH4` to 1 MΩ input impedance.
   * **Sweep Orchestrator (`test_runner.py`)**: Master script is fully documented and ready. It features an adjustable matrix mode to loop over targeted TX/RX pairs across multiple frequencies, automatically logging raw voltage and phase data to CSV.
   * **Data Analysis (`backplane_analysis.ipynb`)**: Designed a complete PyCharm-integrated Jupyter workflow. It successfully splits swept data into Signal Integrity (`TX == RX`) and Crosstalk (`TX != RX`), automatically calculating `Gain_dB` and plotting induced neighbor noise against TTL logic thresholds.

2. **CPLD Hardware (ATF1508AS)**:
   * **Fitted Successfully!** The top-level `zx50_cpld_core` fits into the 128-macrocell CPLD with 96% utilization (124/128).
   * **ROM Bypass Architecture**: Solved the 2K interleaved ROM issue by having the CPLD directly drive `ATL_D[7:0]` with `{4'b0, A[14:11]}` for the lower 32K when Card 0 is booting. This provides a perfect, linear 32K ROM map, bypassing the Address Translation Lookaside (ATL) SRAM completely.
   * **Hardware Write Protection**: The CPLD aggressively protects the ROM chip (preventing accidental EEPROM Software Data Protection triggers) by suppressing `rom_ce_n` and the global `ram_we_n` during writes to the ROM space.
   * **Reset Race Condition Fixed**: `current_id` combinatorial bypass added so sub-modules see DIP switches instantly during reset.
   * **Testbenches**: `zx50_cpld_core_tb` perfectly validates MMU translation, transceivers, ROM bypass, and ROM write protection. `zx50_mem_card_tb` passes basic SRAM integration.

3. **Z80pack Emulator**:
   * **Makefile Cleanup**: Re-written to cleanly output all compiler artifacts (`.o`, `.d`) into a dedicated `../build/` directory.
   * **Memory Encapsulation**: Refactored `simmem.c` and `simmem.h` to de-inline memory arrays, funneling all CPU access through `getmem()` and `putmem()`.
   * **ZX50 Emulation Module**: Drafted `zx50_mem_card.c` to emulate the MMU's `page_ownership` mask, 1MB flat RAM, 32K ROM bypass, and the `0x30` I/O programming interface.

---

## 🚧 Immediate Blocker
* **Awaiting Digikey Parts:** Physical hardware assembly of the Zx50 Bus Probe (Rev A) PCBs is blocked pending component arrival. 

## 🚀 Next Steps (To-Do List)

### 1. Hardware Assembly & Bring-Up
* **Build Boards:** Solder and assemble the Sender and Receiver Zx50 Bus Probe cards once Digikey packages arrive.
* **Flash Pico:** Push the MicroPython `main.py`, `display.py`, and `pin_map.py` to the newly assembled Receiver Pico.
* **Run Sweep:** Execute `test_runner.py` on the live backplane and visualize the real-world RF characteristics in the Jupyter Notebook.

### 2. Verilog Hardware Updates (Memory Card)
* **Create `sst39sf040.v`**: Write a simulation model for the SST39SF040 512KB Flash ROM (similar to the `cy7c1049.v` and `is61c256al.v` SRAM models). It only needs to support basic asynchronous reads for now.
* **Update `zx50_mem_card.v`**: Update the top-level card structural wrapper to instantiate the new SST39SF040 ROM chip, wire up the new `rom_ce_n` output from the CPLD core, and connect it to the physical buses.
* **Update `zx50_mem_card_tb.v`**: Expand the integration testbench to validate reading from the new ROM model using the Card 0 boot bypass.

### 3. Z80pack Emulator Updates
* **Wire up I/O**: Inject `zx50_io_out()` into `z80pack`'s central `simio.c` so the CPU's `OUT` instructions can program the MMU struct.
* **Bootloader Stub**: Write a tiny (< 2KB) Z80 assembly boot stub at `0x0000` that runs out of the ROM bypass. It must program the MMU I/O ports to map upper memory to RAM, copy payloads if necessary, perform a dummy write to `0x0000` to trip the MMU's ROM kill-switch, and jump to the main BASIC cold start.
* **Add DMA Registers**: Implement the Shadow Bus DMA register parser (`0x40 - 0x4F`) inside `zx50_io_out()` in C.


# Zx50 Memory Card & CPLD: Project State Handover

## 1. Project Overview
* **Goal:** A 1MB banked SRAM memory card with a hardware Address Translation Lookaside (ATL) MMU and a cycle-stealing DMA Shadow Bus controller for a Z80 backplane.
* **Target CPLD:** Atmel ATF1508AS-10AU100 (100-pin TQFP, 128 macrocells).
* **PCB:** `Zx50_MemoryCard_RevA` (KiCad).
* **Test Hardware:** Zx50 Bus Probe RevA (Raspberry Pi Pico + 74AHCT541 transceivers).

## 2. Current Status: SYNTHESIS SUCCESS
* **Toolchain Switch:** Quartus II 13.0 Fitter repeatedly failed to route the design due to strict pin locks and PIA congestion. Switched to the **Yosys + Atmel fit1508.exe** open-source toolchain.
* **Result:** The Atmel Fitter successfully routed the full DMA+MMU design using aggressive Foldback paths.
* **Resource Usage:** ~124/128 Macrocells (96% utilization).

## 3. Critical Hardware/PCB Modifications (The "Rev A Bodge")
* **Dedicated Input Trap:** Pins 87, 89, 90, and 92 on the TQFP-100 package are dedicated inputs. They cannot drive outputs.
* **The Bodge:** The KiCad schematic mistakenly routed `RAM_CE0_n` to Pin 90 and `RAM_CE1_n` to Pin 92. 
* **Action Required on Physical PCB:** Cut the traces to 90 and 92. Run bodge wires to **Pin 100** (`RAM_CE0_n`) and **Pin 99** (`RAM_CE1_n`). The CPLD pin constraints have already been updated to reflect this.

## 4. Major Architectural Optimizations Applied
To fit this complex design into 128 macrocells, several extreme optimizations were applied to the Verilog:
1. **DMA 8-Bit Counter:** The 20-bit DMA ripple counter was split. It now only increments the lower 8 bits (`phys_addr_low`), and 4 dead bits (14, 13, 12, 11) are statically masked to `0` to save macrocells.
2. **MMU One-Hot Page Decoding:** The massive 16-to-1 dynamic multiplexer for the `pal_bits` array was eradicated. It is now a 16-bit `page_ownership` register queried via a bitwise AND reduction (`|(page_ownership & decoded_page)`).
3. **Removed `boot_en_n` Hardware Init:** The massive routing fan-out required to preset the 16-bit ownership array caused the router to fail. **The ATL is now hard-zeroed on reset.** 4. **Routing Feedback Loops Broken:** CPLD combinatorial logic no longer relies on physical output pins (like `atl_we_n`) to calculate next-state logic, drastically freeing up the routing matrix.

## 5. Immediate Next Steps (TODOs)
When resuming work, execute these steps in order:
1. **Update Testbenches (Verilog):** Because the `boot_en_n` hardware auto-claim was removed, all testbenches (`zx50_cpld_core_tb.v`, etc.) must be updated. The simulated Z80 must now execute `OUT` instructions to manually program the MMU page ownership before testing memory reads/writes.
2. **Flash the CPLD:** Use JTAG (via `urjtag` or `openocd`) to flash `syn/zx50_cpld_core.svf` to the physical ATF1508AS chip.
3. **Firmware for Bus Probe:** Write a C/C++ or MicroPython script for the Raspberry Pi Pico on the *Zx50 Bus Probe*. Have the Pico bit-bang the Z80 bus to safely test the MMU programming and DMA state machine at slow speeds (e.g., 10 Hz) before plugging in a real 8MHz Z80.
4. **Write Z80 Boot ROM:** The actual Z80 boot code must now include an MMU initialization routine to claim memory pages immediately after reset.
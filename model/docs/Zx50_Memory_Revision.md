
# Architecture Transition: Moving to Lattice MachXO2

For a "V2" board revision, transitioning from a legacy 5V CPLD (like the Atmel ATF1508AS) to a modern 3.3V FPGA architecture provides massive benefits in logic capacity, routing resources, and toolchain reliability. The recommended upgrade path is the **Lattice MachXO2** family.

## 1. The Hardware: Lattice MachXO2
* **Target Part:** LCMXO2-1200HC (or similar).
* **Footprint:** Available in hand-solderable TQFP-100 or TQFP-144 packages, keeping PCB assembly accessible.
* **Logic Capacity:** Provides thousands of LUTs (Look-Up Tables) compared to the 128 macrocells of the ATF1508AS. This eliminates the routing congestion and pin-starvation issues encountered with the full DMA/Arbiter architecture.

## 2. 5V to 3.3V Level Shifting
The MachXO2 is strictly a **3.3V** device and is *not* 5V tolerant on its own. 
* **The Solution:** Because the design already isolates the Z80 bus using 74ABT245 transceivers, transitioning to 3.3V is straightforward. 
* By swapping the `74ABT245` chips for **`74LVC245`** or **`74ALVC164245`** transceivers, the buffers natively handle the 5V (Z80) to 3.3V (FPGA/SRAM) level translation. The FPGA safely operates entirely within a 3.3V domain.

## 3. The Toolchain: Open-Source Perfection
Moving to Lattice completely eliminates the reliance on 20-year-old proprietary DOS executables and Wine wrappers.
* **Synthesis & Routing:** The MachXO2 is fully supported by the modern open-source **Yosys + NextPNR (Project Trellis)** toolchain.
* **Environment:** Native support for Linux and macOS. 
* **Speed:** Lightning-fast synthesis and predictable, modern routing algorithms that do not crash on undefined states (`1'x`).

## 4. Architectural Consolidation (Bonus Benefit)
Because the MachXO2 contains dedicated internal Block RAM (BRAM), **the external ISSI SRAM chip used for the MMU Page LUT can be completely eliminated**. 
* The MMU translation tables can be mapped directly into the FPGA's internal memory.
* This frees up significant PCB real estate, removes an entire parallel memory bus (the `atl_data` and `atl_addr` traces), and dramatically simplifies the internal multiplexing logic.
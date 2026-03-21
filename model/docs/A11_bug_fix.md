Hurray is right! Getting that clean baseline committed to `main` is a huge victory. It gives us a mathematically perfect reference point.

And regarding the PCBA—don't sweat it. Hardware bugs on a first spin are practically a rite of passage, and this exact scenario is why we put a CPLD in the middle of the routing architecture. We are going to save those expensive boards by simply "rewiring" the copper traces in Verilog.

Here is the strategy for organizing and designing the salvage operation.

### 1. Code Organization: Use Compiler Macros (`` `ifdef ``)
I highly recommend **against** creating a separate `src_a11` directory. If you find a bug in the Arbiter's state machine three months from now, having to remember to patch it in two different source trees is a nightmare.

Instead, we should use the Verilog preprocessor. We will wrap the specific wiring changes in an `` `ifdef HW_REV_A11_BUG `` block. 

In your Makefile, you can simply add a second build target (e.g., `make run-tests-a11`) that passes the `-DHW_REV_A11_BUG` flag to the `iverilog` compiler. The testbenches above the card level won't even know the hardware changed, and you maintain a single "source of truth" for your logic.

### 2. The Design Theory: Isolating the Bug
I have fantastic news: **The DMA and MMU state machines do not need to change at all.** We want to keep the DMA module generating a pure, clean, linear 20-bit physical address. We will absorb 100% of the hardware complexity inside the `zx50_cpld_core.v` routing matrix. 

Here is exactly how the CPLD must manipulate the address bits to satisfy the physical wiring of the faulty boards:

**The RAM Rule (The 2K Stripe)**
Because `A11` is physically wired to the SRAM Chip Selects, a 4KB logical page is split in half: the bottom 2KB lives on RAM0, and the top 2KB lives on RAM1.
* **Bank Select:** Driven by the active master's bit 11 (`dma_phys_addr[11]` or `z80_addr[11]`).
* **ATL Data Bus:** For the RAM, the `atl_data` bus represents the 4KB block number. So, the CPLD just passes the pure upper bits: `atl_data = dma_phys_addr[19:12]`. As the DMA address linearly increments, it seamlessly crosses the `A11` chip boundary while keeping the 4K block pointer stable.

**The ROM Rule (The Linear Bypass)**
The Flash ROM is a single chip. It ignores the Chip Select toggle and just wants to see a linear address bus. But because `A11` was stolen for the RAM, the ROM's `A11` pin is physically wired to `atl_data[0]`.
* **If Z80 hits ROM:** The Z80 provides `A[15:0]`. The CPLD must shift the upper bits down to fill the missing `A11` gap. `atl_data` becomes `{3'b000, z80_addr[15:11]}`.
* **If DMA hits ROM:** The DMA provides `A[19:0]`. The CPLD must shift the physical address down by exactly one bit. `atl_data` becomes `dma_phys_addr[18:11]`.

### The Execution
By wrapping the `bank_select` assignment and the `atl_data_out` multiplexer inside an `` `ifdef HW_REV_A11_BUG `` block in the top-level CPLD core, the CPLD acts as a translation layer. It takes the clean, logical intents of the DMA and Z80, and violently shifts and twists them at the very last nanosecond to match the physical copper on your Rev A boards.

Does this align with your understanding of the physical traces? If you are good with this architecture, we can write the macro logic!
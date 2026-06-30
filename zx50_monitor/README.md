# Zx50 Monitor - Session Summary & Resume State

## Programming EEPROM

Remember to add the `-s` flag so minipro will write an undersized ROM image.

```bash
minipro -p SST39SF040 -w monitor.bin -s
```

## 1. Accomplished

We successfully built a cycle-accurate, interactive hardware monitor for the custom Z80 "Zx50" project, fully verified
in the DeZog simulator.

* **CLI & Echo Fix:** Fixed the `Console_Rx` echo bug by correctly restoring the `A` register before transmitting,
  ensuring the CLI echoes typed characters rather than the RAM buffer pointer.
* **Custom DeZog UI:** Migrated from basic output logging to a fully interactive HTML terminal (`sio_ui.html`)
  communicating with a JavaScript hardware emulator (`sio_emulator.js`) using DeZog's `UIAPI`.
* **Hardware Flow Control (Fixing the Race Condition):** Replaced arbitrary assembly delay loops with true hardware flow
  control. The JS emulator holds the SIO `Tx Empty` bit low until DeZog fires `API.uiReady()`, perfectly stalling the
  Z80 at boot until the UI is listening.
* **Front Panel LCD Emulation:** Mapped I/O Port `0x50` to a simulated blue HD44780 LCD in the UI. Added support for
  multi-line text (`0x0A`) and the Clear Display command (`0x01`). The monitor now automatically blasts the current CLI
  input to the LCD when the user presses Enter.
* **D (Dump) Command Math Fix:** Fixed a register clobbering bug in `Cmd_Dump` by properly preserving `DE` (`PUSH DE` /
  `POP DE`) during the `SBC HL, DE` bounds-checking math, allowing multi-line dumps to function perfectly.
* **Hardware Test:** Flash `monitor.bin` to the physical EEPROM and verify that the real silicon behaves exactly like
   the DeZog simulation (serial I/O, LCD routing, and memory dumps).


## 2. Current System Architecture

* **Console SIO (Port A):** Command `0x86`, Data `0x84`. Mapped to the main green terminal UI.
* **Debug SIO (Port B):** Command `0x87`, Data `0x85`. Mapped to the amber `[SYS]` trace in the UI.
* **LCD Front Panel:** Port `0x50`. Mapped to the blue UI display.
* **Memory Map:** Page 0x08 mapped to logical 0x8000 for `CLI_BUFFER`.
* **Executable:** `monitor.bin` (Targeted for EEPROM flashing).

## 3. Next Steps (When Resuming)

1.**G (Go) Command:** Implemented the `G` command to transfer the Program Counter (`JP (HL)`) to a user-specified memory
  address.
2. **Implement 'S' (Set Memory) Command:** Decide on the syntax (Interactive CP/M style vs. Inline Array style) and
   write the routine to poke custom opcodes into RAM.
3. **Implement 'L' (List) Command:** Build the disassembler to translate hex bytes back into readable Z80 opcodes.
4. **Grant Searle MS BASIC:** Once the monitor is complete, use the proven I/O routines to port Grant Searle's Z80 MS
   BASIC to the Zx50 architecture.

## 4. Information Needed to Resume

If starting a completely new chat session, please provide this summary file along with the latest versions of your
assembly files to restore full context:

* `monitor.asm` (Main entry, MMU mapping, Boot sequence)
* `cli.asm` (CLI loop, Command router, Dump/Go routines)
* `io.asm` (SIO/CTC initialization, Tx/Rx polling loops, LCD routines)
* `hex.asm` & `strings.asm` (If modified)
*


# Zx50 Multitasking Operating System Outline

You just outlined the exact architectural blueprint for a modern, preemptive multitasking Z80 Operating System. You are
officially graduating from "ROM Monitor" to "Kernel"!

What you are describing perfectly blends the best parts of CP/M (the transient program area and system calls) with
UNIX-style process isolation. By keeping each program’s stack and state inside its own physical memory page, you isolate
tasks beautifully.

Here is how we can structure the three main pillars of your new OS:

### 1. The Process Control Block (PCB) Table

Instead of a simple FCB, your kernel will maintain a table of **Process Control Blocks (PCBs)** in Logical Page 0. Each
entry will track a program's lifecycle and hardware footprint.

A single PCB record (e.g., 16 bytes) would look like this:

* **Status Byte:** (0 = Empty, 1 = Ready, 2 = Running, 3 = Blocked/Sleeping)
* **Program Name:** 8-byte ASCII string (e.g., `"XMODEM  "`)
* **Physical Page Mapping:** Which physical MMU page(s) this program lives in.
* **Saved Stack Pointer (SP):** The 16-bit address of the program's stack when it was last paused.

### 2. The Context Switch (The 100Hz Magic)

Because every program has its own stack residing in its own physical page, preemptive multitasking becomes incredibly
clean. When your 100Hz RTC interrupt fires, the CPU automatically pushes the Program Counter to the *current program's*
stack.

Your kernel's Interrupt Service Routine (ISR) then does this:

1. **Save State:** `PUSH AF, BC, DE, HL, IX, IY` (and the shadow registers). Now the entire CPU state is safely frozen
   on the app's isolated stack.
2. **Save SP:** Read the Z80's `SP` and save it to the current task's PCB.
3. **Task Select:** Find the next "Ready" task in the PCB table.
4. **MMU Swap:** `OUT` the new task's physical page into the `0x2000` execution window.
5. **Restore State:** Load the Z80's `SP` from the new task's PCB. `POP` all the registers.
6. **Resume:** Execute `RETI`. The CPU seamlessly wakes up inside the new program exactly where it left off.

### 3. The System Call Interface (The ABI)

To keep "user space" programs completely agnostic of your hardware (so they don't care if a character goes out via SIO,
bit-banging, or an LCD), we need an Application Binary Interface (ABI).

The most elegant way to do this on a Z80 is using the **`RST` (Restart)** instructions. `RST` is essentially a 1-byte
hardware `CALL` to a fixed address in Logical Page 0 (e.g., `RST 08H` calls address `0x0008`).

You could establish a standard where user programs load a "Syscall Number" into register `C`, and then execute
`RST 08H`.

* `LD C, 0x01` / `RST 08H` -> Read character to `A`.
* `LD C, 0x02` / `RST 08H` -> Write character in `A` to console.
* `LD C, 0x10` / `RST 08H` -> Yield remainder of time slice to OS.

The kernel intercepts `RST 08H`, looks at `C`, and jumps to the low-level hardware drivers.

# More on paging

3. PCB Paging (Virtual Memory)
This is the holy grail. It turns your simple DOS into a true paged OS (like CP/M 3.0).

How it works: We add a Page byte to PCB_Entry. We write a simple memory manager that knows which of the 16 physical pages are in use.

The architecture: Every single app can be compiled to ORG 0x4000.

When you run xm, the OS finds a free physical page (e.g., Page 4), maps it to the 0x4000 window, downloads the file, and then unmaps it.

When you run the app, the OS looks at the PCB, maps physical Page 4 back into the 0x4000 slot, and CALLs it. When the app RETurns, the OS unmaps it.

The benefit: You never have to worry about memory address collisions again, and apps are completely sandboxed from one another.

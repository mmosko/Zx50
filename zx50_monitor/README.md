# Zx50 Monitor - Session Summary & Resume State

## 1. Accomplished

We successfully built a cycle-accurate, interactive hardware monitor for the custom Z80 "Zx50" project, fully verified
in the DeZog simulator.

* **CLI & Echo Fix:** Fixed the `Console_Rx` echo bug by correctly restoring the `A` register before transmitting,
  ensuring the CLI echoes typed characters rather than the RAM buffer pointer.
* **G (Go) Command:** Implemented the `G` command to transfer the Program Counter (`JP (HL)`) to a user-specified memory
  address.
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

## 2. Current System Architecture

* **Console SIO (Port A):** Command `0x86`, Data `0x84`. Mapped to the main green terminal UI.
* **Debug SIO (Port B):** Command `0x87`, Data `0x85`. Mapped to the amber `[SYS]` trace in the UI.
* **LCD Front Panel:** Port `0x50`. Mapped to the blue UI display.
* **Memory Map:** Page 0x08 mapped to logical 0x8000 for `CLI_BUFFER`.
* **Executable:** `monitor.bin` (Targeted for EEPROM flashing).

## 3. Next Steps (When Resuming)

1. **Hardware Test:** Flash `monitor.bin` to the physical EEPROM and verify that the real silicon behaves exactly like
   the DeZog simulation (serial I/O, LCD routing, and memory dumps).
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
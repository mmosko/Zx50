# Zx50 Monitor - Session Summary & Resume State

## Programming EEPROM

Remember to add the `-s` flag so minipro will write an undersized ROM image.

```bash
minipro -p SST39SF040 -w monitor.bin -s
```

## 1. Accomplished

We have successfully transitioned from a basic ROM monitor to a stable, self-hosting Operating System kernel capable of downloading, verifying, and executing third-party user-space applications.

* **Dedicated Hardware Clock:** Upgraded the system clock from an Arbitrary Function Generator (AFG) to a dedicated 20MHz oscillator mezzanine. A hardware counter divides this to provide a mathematically perfect 50% duty cycle, 5.000 MHz `ZCLK` baseline.
* **Interrupt-Driven I/O Planning:** Designed a lock-free Single-Producer/Single-Consumer (SPSC) ring buffer architecture to transition the OS from polled serial I/O to fully asynchronous background processing. Engineered a solution to the "Lost Wakeup" race condition using the Z80's native `EI` delay and `HALT` instructions (Detailed in `TTY.md`).
* **Hardware Boot & Memory Paging:** Fixed the `LDIR` register clobbering bug. The physical silicon now successfully maps a 16KB copy window, copies the ROM to SRAM, and executes the "Phantom Jump" to swap out the ROM completely.
* **XMODEM Native File Transfer:** Built a robust, state-machine-driven XMODEM receiver (`apps/xmodem.z80`). It features hardware-accurate polling, adjustable timeout loops to prevent USB NAK-storms, and real-time padding.
* **The PCB & Memory Auditing:** Implemented a Process Control Block (PCB) table in Logical Page 0. When an app is downloaded, the kernel calculates a 16-bit cumulative checksum and logs its exact memory footprint.
* **Kernel Memory Protection:** The XMODEM loader now strictly enforces boundary checks. It actively rejects any attempt to load an executable below `0x2000`, safeguarding the kernel and stack from user-space corruption.
* **The `verify` Command:** Abstracted the checksum math into `pcb_verify.z80`. The CLI `v[erify] <name>` command seamlessly recalculates the payload in SRAM and compares it against the PCB to detect bit-rot or memory corruption before execution.
* **The Zx50 SDK:** Established a formal Page 0 jump table (`syscall.z80`) and wrote the `DEVGUIDE.md`. Developers can write hardware-agnostic standalone `.bin` applications (like `hello.z80`) that compile entirely outside the kernel tree.

## 2. Current System Architecture

### Hardware

Netlists are available under individual card projects in `zx50/boards/`.

| Slot | Card                                          |
|:----:|:---------------------------------------------:|
| n/a  | Zx50_Backplane_RevD                           | 
| n/a  | Zx50_FrontPanelDisplay                        |
| 1    | Zx50_Cpu_RevB1 + Zx50_Clock_Mezzanine_RevC    |
| 2    | Zx50_Serial_RevB                              |
| 3    | Zx50_MemoryCard_RevA1 (with EEPROM)           |
| 4    | (reserved 2nd memory card)                    |
| 5    | empty                                         |
| 6    | Zx50_FrontPanelCard_RevB                      |
| 7    | Zx50_Bus_Probe_RevB                           |
| 8    | empty                                         |

Note: 
- slot 8 has some oscilliscope probes on ZCLK and MCLK. 
- Bus Analyzer is connected to bus probe Z80 Data (J16) and Z80 Contro (J17)l


* **System Clock:** 10.000 MHz `ZCLK` (Divided from 40MHz `MCLK`).
* **Console SIO (Port A):** Command `0x86`, Data `0x84`.
* **Debug SIO (Port B):** Command `0x87`, Data `0x85`. 
* **LCD Front Panel:** Port `0x50`. Mapped to the blue UI display.
* **MMU (Port 0x30):** 4KB physical pages mapped to 16 logical windows.
* **Kernel RAM Layout:** * `0x0000 - 0x0FFF`: The Operating System, PCB Table, and Jump Table API.
  * `0x1000 - 0x1FFF`: The Stack (grows downward from `0x2000`).
  * `0x2000 - 0xFFFF`: User Space / Transient Program Area (TPA).

## 3. Code Layout

The project enforces a strict separation of concerns between the kernel, the shell, built-in apps, and user-space binaries.

```text
zx50_monitor/
├── apps/               # Third-party user-space programs
│   ├── DEVGUIDE.md     # SDK documentation and memory contracts
│   └── hello.z80       # Example standalone application
├── kernel/             # Core OS components
│   ├── apps/           # Built-in kernel utilities
│   │   ├── ddt.z80     # Debugger
│   │   └── xmodem.z80  # Serial file transfer protocol
│   ├── io/             # I/O related activities
│   |   ├── io.z80      # Hardware drivers (SIO, LCD)
│   |   └── ring_buffer.z80 # Lock-free SPSC memory queues
│   ├── pcb/            # Process Control Block logic
│   │   ├── pcb_verify.z80
│   │   └── pcb.z80
│   ├── defines.z80     # System-wide memory & port constants
│   ├── hex.z80         # Hexadecimal parsing & math
│   └── strings.z80     # String manipulation
├── shell/              # Command Line Interface
│   ├── cli.z80         # Main prompt and routing loop
│   ├── cmd_list.z80    # 'l' command
│   ├── cmd_run.z80     # 'r' command
│   ├── cmd_verify.z80  # 'v' command
│   └── readline.z80    # Buffer and backspace handling
├── monitor.z80         # Main bootloader, MMU init, and API Jump Table
├── syscall.z80         # The SDK include file for user apps
├── sio_emulator.js     # DeZog hardware simulation logic
├── sio_ui.html         # DeZog interactive terminal UI
├── README.md           # This file
└── TTY.md              # OS Asynchronous Serial / TTY Architecture Plan
```

## 4. Next Steps (When Resuming)

1. **Implement Ring Buffers:** Integrate the `ring_buffer.z80` logic into the kernel, allocate the 4 instances in Page 0 RAM, and update the syscalls (`Sys_ReadChar`, `Sys_PrintChar`) to use the blocking `HALT` wrappers.
2. **SIO Interrupt Configuration:** Refactor SIO initialization (`io.z80`) to enable IM2 interrupts with the "Status Affects Vector" routing.
3. **ISRs & Line Disciplines:** Write the SIO Rx/Tx Interrupt Service Routines. Implement the Raw/Cooked mode state tracking to allow the Rx ISR to intercept `0x03` (Ctrl+C) and forcibly break infinite loops, returning to the CLI.
4. **PCB Paging (Virtual Memory):** Add a `Page` byte to the `PCB_Entry`. Modify the `xm` and `run` commands to dynamically allocate free physical memory pages, map them into the `0x4000` execution window, and unmap them upon exit to achieve true process isolation.
5. **Multitasking Scheduler:** Leverage the CTC Channel 3 (100Hz) interrupt and the isolated physical pages to implement CP/M 3.0 / UNIX-style preemptive context switching between multiple concurrent applications.

# More on paging

* PCB Paging (Virtual Memory)

This is the holy grail. It turns your simple DOS into a true paged OS (like CP/M 3.0).

How it works: We add a Page byte to PCB_Entry. We write a simple memory manager that knows which of the 16 physical pages are in use.

The architecture: Every single app can be compiled to ORG 0x4000.

When you run xm, the OS finds a free physical page (e.g., Page 4), maps it to the 0x4000 window, downloads the file, and then unmaps it.

When you run the app, the OS looks at the PCB, maps physical Page 4 back into the 0x4000 slot, and CALLs it. When the app RETurns, the OS unmaps it.

The benefit: You never have to worry about memory address collisions again, and apps are completely sandboxed from one another.

## 5. Change History

### 2026-09-13: Serial Driver & Boot Interrupt Fixes
* **Decoupled RTS/CTS Hardware Handshaking:** Removed `SIO_WR3_AUTO_EN` (Auto Enables) from Channel A (Console) and Channel B (Debug) receiver configurations in `kernel/io/serial.z80`. The SIO transmitter now operates freely without requiring an external active-low assertion on `~CTS`, and the receiver does not require `~DCD`.
* **Resolved Premature Boot Interrupts:** Removed `DI` and `EI` instructions from `PrintStringLCD` and `PrintNullStringLCD` in `kernel/io/lcd.z80`. Previously, printing the initial memory boot banner triggered `EI` before the Interrupt Vector Table (`I`), `IM 2`, CTC, and SIO vector base were initialized.
* **Added `SIO_CMD_RST_TX_INT` to `SIO_A_Tx_ISR`:** Added WR0 command `0x28` (`SIO_CMD_RST_TX_INT`) to the `.buffer_empty` handler in `SIO_A_Tx_ISR` to formally reset the SIO's internal transmit interrupt pending latch when the ring buffer runs dry.
* **Dynamic Tx Interrupt Enabling:** Changed `Init_SIO` and `SetTermMode_Inner` so Channel A starts with Tx interrupts disabled in WR1. `Console_Tx` dynamically enables `SIO_WR1_TX_INT_EN` only when bytes are queued in `PORT_A_TX_RB`, and `SIO_A_Tx_ISR` disables it upon draining.
* **Disabled Unused Channel B Tx Interrupts:** Cleared `SIO_WR1_TX_INT_EN` from Channel B, as debug output is synchronously polled via `Debug_Tx`.

## 6. Hardware TODOs & Board Rework

* [ ] **Zx50_Serial_RevB RTS/CTS Handshake Support:**
  * **`DCDA` (Pin 19):** Currently unconnected/floating on `IC2`. Tie to GND or add a 10k pull-down to prevent the receiver from stalling when `Auto Enables` is active.
  * **`CTSA` (Pin 18):** Currently routed only to header `J4 pin 5` and `J3 pin 7` without a pull-down resistor. Add a 10k pull-down so the transmitter remains enabled when connecting via simple 3-wire serial cables (TX/RX/GND).
  * **Firmware Auto-Enables:** Once the pull-downs or jumper options are verified on the board, restore `SIO_WR3_AUTO_EN` in `kernel/io/serial.z80` to re-enable optional hardware flow control.
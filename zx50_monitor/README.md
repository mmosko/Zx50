# Zx50 Monitor - Session Summary & Resume State

## Programming EEPROM

Remember to add the `-s` flag so minipro will write an undersized ROM image.

```bash
minipro -p SST39SF040 -w monitor.bin -s
```

## 1. Accomplished

We have successfully transitioned from a basic ROM monitor to a stable, self-hosting Operating System kernel capable of downloading, verifying, and executing third-party user-space applications.

* **Hardware Boot & Memory Paging:** Fixed the `LDIR` register clobbering bug. The physical silicon now successfully maps a 16KB copy window, copies the ROM to SRAM, and executes the "Phantom Jump" to swap out the ROM completely.
* **XMODEM Native File Transfer:** Built a robust, state-machine-driven XMODEM receiver (`apps/xmodem.z80`). It features hardware-accurate polling (`Console_Poll`), adjustable timeout loops to prevent USB NAK-storms, and real-time padding.
* **The PCB & Memory Auditing:** Implemented a Process Control Block (PCB) table in Logical Page 0. When an app is downloaded, the kernel calculates a 16-bit cumulative checksum and logs its exact memory footprint.
* **Kernel Memory Protection:** The XMODEM loader now strictly enforces boundary checks. It actively rejects any attempt to load an executable below `0x2000`, safeguarding the kernel and stack from user-space corruption.
* **The `verify` Command:** Abstracted the checksum math into `pcb_verify.z80`. The CLI `v[erify] <name>` command seamlessly recalculates the payload in SRAM and compares it against the PCB to detect bit-rot or memory corruption before execution.
* **The Zx50 SDK:** Established a formal Page 0 jump table (`syscall.z80`) and wrote the `DEVGUIDE.md`. Developers can now write hardware-agnostic standalone `.bin` applications (like `hello.z80`) that compile entirely outside the kernel tree.

## 2. Current System Architecture

* **Console SIO (Port A):** Command `0x86`, Data `0x84`.
* **Debug SIO (Port B):** Command `0x87`, Data `0x85`. 
* **LCD Front Panel:** Port `0x50`. Mapped to the blue UI display.
* **MMU (Port 0x30):** 4KB physical pages mapped to 16 logical windows.
* **Kernel RAM Layout:** 
  * `0x0000 - 0x0FFF`: The Operating System, PCB Table, and Jump Table API.
  * `0x1000 - 0x1FFF`: The Stack (grows downward from `0x2000`).
  * `0x2000 - 0xFFFF`: User Space / Transient Program Area (TPA).

## 3. Code Layout

The project has been refactored to enforce a strict separation of concerns between the kernel, the shell, built-in apps, and user-space binaries.

```text
zx50_monitor/
├── apps/               # Third-party user-space programs
│   ├── DEVGUIDE.md     # SDK documentation and memory contracts
│   └── hello.z80       # Example standalone application
├── kernel/             # Core OS components
│   ├── apps/           # Built-in kernel utilities
│   │   ├── ddt.z80     # Debugger
│   │   └── xmodem.z80  # Serial file transfer protocol
│   ├── pcb/            # Process Control Block logic
│   │   ├── pcb_verify.z80
│   │   └── pcb.z80
│   ├── defines.z80     # System-wide memory & port constants
│   ├── hex.z80         # Hexadecimal parsing & math
│   ├── io.z80          # Hardware drivers (SIO, LCD)
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
└── sio_ui.html         # DeZog interactive terminal UI
```

## 4. Next Steps (When Resuming)

1. **Hardware Interruption (`^C` Handler):** Configure the Z80 CTC to fire a 100Hz hardware tick. Use this interrupt to build an ISR that catches `0x03` (Ctrl+C) on the serial line to forcibly break infinite loops and return to the CLI.
2. **PCB Paging (Virtual Memory):** Add a `Page` byte to the `PCB_Entry`. Modify the `xm` and `run` commands to dynamically allocate free physical memory pages, map them into the `0x4000` execution window, and unmap them upon exit to achieve true process isolation.
3. **Multitasking Scheduler:** Leverage the 100Hz RTC interrupt and the isolated physical pages to implement CP/M 3.0 / UNIX-style preemptive context switching between multiple concurrent applications.

# More on paging

* PCB Paging (Virtual Memory)

This is the holy grail. It turns your simple DOS into a true paged OS (like CP/M 3.0).

How it works: We add a Page byte to PCB_Entry. We write a simple memory manager that knows which of the 16 physical pages are in use.

The architecture: Every single app can be compiled to ORG 0x4000.

When you run xm, the OS finds a free physical page (e.g., Page 4), maps it to the 0x4000 window, downloads the file, and then unmaps it.

When you run the app, the OS looks at the PCB, maps physical Page 4 back into the 0x4000 slot, and CALLs it. When the app RETurns, the OS unmaps it.

The benefit: You never have to worry about memory address collisions again, and apps are completely sandboxed from one another.

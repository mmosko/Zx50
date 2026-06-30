# Zx50 Operating System: Application Developer Guide

Welcome to the Zx50 SDK. This guide outlines the architectural rules, memory contracts, and system APIs required to write native, bare-metal C or Assembly applications for the Zx50 Operating System.

## Core Architectural Rules

* **Execution Origin:** Applications must be compiled to the exact logical memory address they will be loaded into (e.g., `ORG 0x4000`).
* **Clean Exits:** The OS invokes applications via a standard Z80 `CALL`. Your application must exit by executing a `RET` instruction to safely return control to the OS Shell.
* **Argument Passing:** Upon execution, the OS passes a pointer to any command-line arguments via the `DE` register. If no arguments were provided, `DE` points to a NULL (`0x00`) byte.
* **System Calls:** Applications must include `syscall.z80` to route API requests to the Kernel's Page 0 jump table.

---

## Memory & The Checksum Contract

The Zx50 kernel calculates a 16-bit cumulative checksum of your binary file the moment it is downloaded into RAM via XMODEM. To prevent your application from failing future memory validations, you must strictly separate your executable code from your mutable state.

* **Read-Only Data:** Code and static strings (`DB`, `DW`, `TEXT`) should be placed normally within your application flow.
* **Mutable Variables:** All mutable, uninitialized variables MUST be defined at the absolute end of your source file using the `DS` (Define Space) directive. 

Because `DS` simply increments the assembler's memory pointers without generating physical bytes in the compiled `.bin` file, these variables will exist safely in RAM *after* the downloaded footprint, keeping your file's runtime checksum completely intact.

---

## The App Skeleton

```assembly
    DEVICE NOSLOT64K
    OUTPUT "myapp.bin"
    
    ORG 0x4000          ; Must match the XMODEM target address

App_Main:
    ; DE contains the pointer to any CLI arguments
    
    LD HL, MSG_HELLO
    CALL SYS_PRINTSTR   ; Print to the console
    
    RET                 ; Return cleanly to the Zx50 OS Shell

; --- Read-Only Data ---
MSG_HELLO:
    DB "Hello, Zx50!", 0x0D, 0x0A, 0x00
    
    INCLUDE "syscall.z80" 

; --- Mutable Variables (Must be at the end!) ---
App_Counter:    DS 1
App_Buffer:     DS 64
```

---

## Zx50 System API Reference

Include `syscall.z80` to access the following Kernel APIs.

| Macro | Input | Output | Purpose |
| :--- | :--- | :--- | :--- |
| **`SYS_READCHAR`** | None | `A` = Char | Blocks and waits for a single character. |
| **`SYS_POLLCHAR`** | None | `A` = Char, `C` Flag | Non-blocking read. Carry Flag is SET if no data. |
| **`SYS_PRINTCHAR`**| `A` = Char | None | Prints a single character to the console. |
| **`SYS_PRINTSTR`** | `HL` = String | None | Prints a NULL-terminated string. |
| **`SYS_PARSEHEX`** | `HL` = String | `DE` = Value, `C` Flag | Parses hex string to 16-bit value. Carry Flag is SET on error. |
| **`SYS_PARSESTR`** | `HL` = String, `DE` = Dest | `HL` = Delimiter | Extracts an argument string into a buffer. |
| **`SYS_REG_APP`** | `HL` = Name, `DE` = Addr | `C` Flag | Registers an app to the OS table. Carry Flag SET if full. |
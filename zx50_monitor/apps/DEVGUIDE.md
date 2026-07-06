# Zx50 Operating System: Application Developer Guide

Welcome to the Zx50 SDK. This guide outlines the architectural rules, memory contracts, and system APIs required to write native, bare-metal C or Assembly applications for the Zx50 Operating System.

## Core Architectural Rules

* **Execution Origin:** Applications must be compiled to the exact logical memory window provided by the OS (currently `ORG 0x4000`).
* **The Executable Header:** Every application must begin with the Zx50 Standard Header. This defines the memory segments so the OS can safely allocate the stack and track your mutable data.
* **Clean Exits:** The OS invokes applications via a standard Z80 `CALL`. Your application must exit by executing a `RET` instruction (or calling `Sys_Exit`) to safely return control to the OS Shell.
* **Argument Passing:** Upon execution, the OS passes a pointer to any command-line arguments via the `DE` register. If no arguments were provided, `DE` points to a NULL (`0x00`) byte.
* **System Calls:** Applications must include `syscall.z80` to route API requests to the Kernel's Page 0 jump table.
* **Shadow Register Ban:** Applications **MUST NOT** use the Z80 shadow registers (`EXX` and `EX AF, AF'`). The Kernel reserves the alternate register bank exclusively for high-speed background Interrupt Service Routines (ISRs). If an application attempts to store state in the shadow registers, it will be asynchronously overwritten and corrupted by the OS.

---

## Memory Segments & The Checksum Contract

The Zx50 kernel calculates a 16-bit cumulative checksum of your binary file when it is downloaded into RAM. To prevent your application from failing future memory validations, you must strictly define your segments in the header:

* **Code Segment (CS):** Your read-only executable instructions and static strings.
* **Data Segment (DS):** Your uninitialized, mutable variables. Defined at the end of your file using the `DS` directive. Because this data is defined in the header, the OS knows not to include it in the file checksum.
* **Stack Segment (SS):** The Zx50 kernel isolates hardware interrupts on its own kernel stack. In the header, you must specify where you want your application's Stack Pointer (SP) to begin (e.g., `0x7FFE`, the top of your allocated 16KB memory page).

---

## The App Skeleton (Standard Header)

To compile successfully for the Zx50, your application must perfectly mirror this structure.

```assembly
    DEVICE NOSLOT64K
    OUTPUT "myapp.bin"
    
    ORG 0x4000          ; Must match the OS execution window

    ; =========================================================================
    ; 1. Zx50 STANDARD EXECUTABLE HEADER (Must be exactly at 0x4000)
    ; =========================================================================
    JP App_Main         ; Offset 0x00: Execution jump (3 bytes)
    
    ; --- Metadata ---
    DW App_Data_Start   ; Offset 0x03: Start of mutable Data Segment (DS)
    DW App_Data_Size    ; Offset 0x05: Length of mutable data
    DW 0x7FFE           ; Offset 0x07: Requested Stack Pointer (SS/SP)
    DW 0x0000           ; Offset 0x09: Reserved for SIGINT (^C) handler address
    
    ; Pad header to exactly 16 bytes for future OS expansion
    BLOCK 16 - ($ - 0x4000), 0x00 

    ; =========================================================================
    ; 2. CODE SEGMENT (CS)
    ; =========================================================================
App_Main:
    ; The OS has already set SP to 0x7FFE based on your header.
    ; DE contains the pointer to any CLI arguments.
    
    LD HL, MSG_HELLO
    CALL SYS_PRINTSTR   ; Print to the console
    
    RET                 ; Return cleanly to the OS Shell

MSG_HELLO:
    DB "Hello, Zx50!", 0x0D, 0x0A, 0x00
    
    INCLUDE "syscall.z80" 

    ; =========================================================================
    ; 3. DATA SEGMENT (DS)
    ; =========================================================================
App_Data_Start:
App_Counter:    DS 1
App_Buffer:     DS 64
App_Data_Size   EQU $ - App_Data_Start
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
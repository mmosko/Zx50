    DEVICE NOSLOT64K
;    SLDOPT COMMENT WPMEM, LOGPOINT, ASSERTION  ; Enables DeZog advanced debugging
    SLDOPT COMMENT WPMEM, ASSERTION  ; Enables DeZog advanced debugging
    OUTPUT "monitor.bin"
    ORG 0x0000

    INCLUDE "defines.asm"

    ; ==========================================
    ; MEMORY MAP
    ; 0x0000 - 0x2000 : Reserved for Monitor Program (8KB)
    ;    0x0000 - 0x0FFF : logical page 0 (the operating system)
    ;    0x1000 - 0x1FFF : logical page 1 (stack)
    ; 0x2000 - 0xFFFF : program RAM (logical pages 2-15)
    ; ==========================================


Boot:
    DI                  ; 1. Disable interrupts before anything else
    
    ; ==============================
    ; Map physical RAM page 0 to logical page 8 (0x8000)
    ; Copy the ROM to RAM
    ; Map physical RAM page 0 to logical page 0 (0x0000)
    ; Then initialize the reset of memory, setup the stack pointer, etc.
    ;
    ; TODO: This assumes the ROM is less than 4K
    ; ==============================

RomToRam:    
    LD C, MMU_PORT      ; C = MMU I/O Port

    ; --- Map Physical RAM Page 0 to Logical Page 8 (0x8000) ---
    ; The logical page is the upper nibble of B
    LD B, 0x80          ; B = Start logical page 8 (A15:A12 = 1000)
    LD A, 0x00          ; Physical page (0-255)
    OUT (C), A          ; Map it to the 0x8000 window

    ; --- Copy the ROM to RAM ---
    LD HL, 0x0000       ; Source: Start of ROM (Logical 0x0000)
    LD DE, 0x8000       ; Destination: Physical RAM Page 0 (Logical 0x8000)
    LD BC, _END_OF_ROM  ; Length: Automatically calculated by the assembler
    LDIR                ; Execute block copy. (HL, DE, BC auto-update)

    ; --- The Phantom Jump ---
    ; We are currently executing from EEPROM at Logical Page 0.
    ; We are about to swap Physical RAM Page 0 over top of it.
    
    LD B, 0x00          ; Logical page 0
    LD A, 0x00          ; Physical page 0
    OUT (C), A          ; ROM is gone, RAM is now mapped at 0x0000.

    ; =============================
    ; --- Zero out the variables area ---
    ; =============================
    LD HL, _END_OF_ROM
    LD BC, MONITOR_STORAGE_SIZE  ; Length of CLI_BUFFER + LAST_DUMP_ADDR

ZeroRAM:
    LD (HL), 0x00
    INC HL
    DEC BC
    LD A, B
    OR C
    JR NZ, ZeroRAM

    ; =============================
    ; Now do a linear map of physical page 1-15 to logical page 1-15 (0x1000-0xF000)
    ; ============================= 

    LD B, 0x10          ; B = Start logical page 1
    LD D, 0x01          ; D = Start physical RAM page 1

MapRAM:
    LD A, D             
    OUT (C), A          ; Trigger mmu_direct_wr: Map physical page D to logical window B
    INC D               ; Next physical page (0x09, 0x0A...)
    LD A, B
    ADD A, 0x10         ; Next logical window (0x10 -> 0x20 -> 0x30...)
    LD B, A
    JR NC, MapRAM       ; Loop until B overflows from 0xF0 to 0x00 (Carry flag sets)

    ; 3. Establish the Stack
    LD SP, STACK_POINTER    ; Stack starts at 8K and works down.

    LD HL, MSG_MEM_INIT     ; Point HL to the first string
    CALL PrintStringLCD     ; Blast it to the LCD

    ; --- Hardware Initialization ---
    CALL Init_CTC
    CALL Init_SIO

    ; --- Boot Banners ---
    LD HL, MSG_SIO_READY
    CALL PrintStringLCD

    LD HL, MSG_CONSOLE_BANNER
    CALL PrintConsoleString
    LD HL, MSG_DEBUG_BANNER
    CALL PrintDebugString

    ; --- Jump to the Command Line Interface ---
    JP Init_CLI

    ; ==========================================
    ; Source File Inclusions
    ; ==========================================
    INCLUDE "io.asm"
    INCLUDE "cli.asm"
    INCLUDE "hex.asm"
    INCLUDE "strings.asm"

_END_OF_ROM: 
    ; The assembler assigns this label the exact address of the last byte + 1.

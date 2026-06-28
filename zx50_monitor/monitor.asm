    DEVICE NOSLOT64K
;    SLDOPT COMMENT WPMEM, LOGPOINT, ASSERTION  ; Enables DeZog advanced debugging
    SLDOPT COMMENT WPMEM, ASSERTION  ; Enables DeZog advanced debugging
    OUTPUT "monitor.bin"
    ORG 0x0000

    INCLUDE "defines.asm"

Boot:
    DI                  ; 1. Disable interrupts before anything else
    
    ; 2. Map Physical RAM (Pages 0x08-0x0F) to Logical Upper 32K (0x8000-0xFFFF)
    LD C, MMU_PORT      ; C = MMU I/O Port
    LD B, 0x80          ; B = Start logical page 8 (A15:A12 = 1000)
    LD D, 0x08          ; D = Start physical RAM page 0x08

MapRAM:
    LD A, D             
    OUT (C), A          ; Trigger mmu_direct_wr: Map physical page D to logical window B
    INC D               ; Next physical page (0x09, 0x0A...)
    LD A, B
    ADD A, 0x10         ; Next logical window (0x80 -> 0x90 -> 0xA0...)
    LD B, A
    JR NC, MapRAM       ; Loop until B overflows from 0xF0 to 0x00 (Carry flag sets)

    ; 3. Establish the Stack
    LD SP, 0x0000       ; PUSH decrements SP before writing. First push goes to 0xFFFF and 0xFFFE.

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

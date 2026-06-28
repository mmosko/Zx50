; --------------------------------------------------------------------------------
; CLI Processor
; --------------------------------------------------------------------------------

Init_CLI:
    ; Print the command prompt before waiting for input
    LD HL, MSG_PROMPT
    CALL PrintConsoleString

    LD HL, CLI_BUFFER       ; Point HL to the start of the RAM buffer

CliLoop:
    CALL Console_Rx         ; Wait for user keystroke
    LD E, A                 ; Save character in E
    
    ; 1. Is it Enter (0x0D)?
    CP 0x0D
    JR Z, ProcessLine
    
    ; 2. Is it Backspace (0x08) or Delete (0x7F)?
    CP 0x08
    JR Z, HandleBackspace
    CP 0x7F
    JR Z, HandleBackspace
    
    ; 3. Check for Buffer Overflow!
    LD A, L
    CP LOW(CLI_BUFFER_END)  ; Does L match the end address lower byte?
    JR NZ, .store_char      ; If not, safe to store
    LD A, H
    CP HIGH(CLI_BUFFER_END) ; Does H match the end address upper byte?
    JR Z, BufferFull        ; If both match, we are out of space!

.store_char:
    ; 4. Otherwise, it's a normal character. Store and echo.
    LD (HL), E              ; Store character in RAM
    INC HL                  ; Advance buffer pointer
    LD A, E                 ; Restore the character into A!    
    CALL Console_Tx         ; Echo the character to the user's screen
    JR CliLoop              ; Wait for next key

BufferFull:
    ; Send an ASCII Bell (0x07) to the terminal to warn the user
    LD A, 0x07
    CALL Console_Tx
    JR CliLoop              ; Go back to waiting (allows them to backspace)

HandleBackspace:
    ; 4a. Check if we are already at the start of the buffer
    ; (Compare HL to CLI_BUFFER. We check L first, then H)
    LD A, L
    CP LOW(CLI_BUFFER)      ; Is the lower byte 0x00?
    JR NZ, .do_bs           ; If not, it's safe to backspace
    LD A, H
    CP HIGH(CLI_BUFFER)     ; Is the upper byte 0x80?
    JR Z, CliLoop           ; If both are true, we are at the start. Ignore!

.do_bs:
    ; 4b. Move the RAM pointer back by one
    DEC HL              
    
    ; 4c. Visually erase the character on the terminal (BS, Space, BS)
    LD A, 0x08
    CALL Console_Tx
    LD A, 0x20
    CALL Console_Tx
    LD A, 0x08
    CALL Console_Tx
    
    JR CliLoop

ProcessLine:
    ; Null-terminate the string in the RAM buffer
    LD (HL), 0x00           
    
    ; --- BLAST TO LCD ---
    ; Clear the LCD first so the new command doesn't append to old text
    LD A, 0x01
    OUT (LCD_PORT), A       
    
    ; Print the newly null-terminated command buffer
    LD HL, CLI_BUFFER
    CALL PrintNullStringLCD 
    ; --------------------

    ; Drop the Console cursor to a new line (\r\n)
    LD HL, MSG_CRLF
    CALL PrintConsoleString

    ; Read the first character from the buffer to determine the command
    LD HL, CLI_BUFFER
    LD A, (HL)

    ; Ignore empty lines (user just pressed Enter)
    OR A                    ; Is it 0x00?
    JR Z, Init_CLI

    ; Routing Table
    CP '?'
    JR Z, Cmd_Help
    CP 'h'
    JR Z, Cmd_Help
    CP 'H'
    JR Z, Cmd_Help

    CP 'd'
    JR Z, Cmd_Dump
    CP 'D'
    JR Z, Cmd_Dump

    CP 'q'
    JR Z, Cmd_Quit
    CP 'Q'
    JR Z, Cmd_Quit

    ; If we get here, the command is unknown
Cmd_Unknown:
    LD HL, MSG_UNKNOWN
    CALL PrintConsoleString
    JP Init_CLI

; =============================================================================
; Command Subroutines
; =============================================================================

Cmd_Help:
    LD HL, MSG_HELP
    CALL PrintConsoleString
    JP Init_CLI

; =============================================================================
; Subroutine: Cmd_Quit
; Purpose:    Halt the program (useful in zsim debugger)
; =============================================================================

Cmd_Quit:
    LD HL, MSG_LCD_HALT
    CALL PrintStringLCD
    LD HL, MSG_QUIT
    CALL PrintConsoleString
    HALT

; =============================================================================
; Subroutine: Cmd_Dump
; Purpose:    Prints memory contents
; =============================================================================

Cmd_Dump:
    INC HL              ; Skip the 'D'

.skip_spaces:
    LD A, (HL)
    CP ' '
    JR NZ, .check_args  ; If not a space, check what it is
    INC HL
    JR .skip_spaces

.check_args:
    OR A                ; Did we hit the end of the string?
    JR NZ, .parse_start 
    
    ; --- No arguments provided! Load from LAST_DUMP_ADDR ---
    LD HL, (LAST_DUMP_ADDR)
    LD B, H
    LD C, L
    JR .set_default_end

.parse_start:
    ; --- Parse the Start Address ---
    CALL ParseHexWord
    JR C, Cmd_Unknown   ; Abort if invalid hex
    LD B, D             ; Store Start Address in BC
    LD C, E

    LD A, (HL)
    CP ','              ; Is there a comma (End Address)?
    JR Z, .parse_end

.set_default_end:
    ; --- No End Address. Default = Start + 0x00FF (256 bytes) ---
    LD H, B
    LD L, C
    LD DE, 0x00FF
    ADD HL, DE
    LD D, H
    LD E, L
    JR .execute

.parse_end:
    ; --- Parse the End Address ---
    INC HL              ; Skip the ','
    CALL ParseHexWord
    JR C, Cmd_Unknown

.execute:
    ; --- Execution Loop ---
    LD H, B             ; Move Current Address into HL for DumpLine
    LD L, C

.dump_loop:
    CALL DumpLine       ; Dumps 16 bytes and advances HL by 16

    ; Did we pass the End Address (DE)?
    ; We check this by doing: DE - HL. If it carries/borrows, HL > DE.
    PUSH HL
    PUSH DE              ; Save the End Address!
    EX DE, HL           ; HL = End Address, DE = Current Address
    OR A                ; Clear Carry Flag
    SBC HL, DE          ; End - Current
    POP DE              ; Restore the End Address!
    POP HL              ; Restore Current Address into HL
    
    JR NC, .dump_loop   ; If no carry, End >= Current. Keep looping!

    ; --- Save our place for the next 'D' command ---
    LD (LAST_DUMP_ADDR), HL
    
    JP Init_CLI

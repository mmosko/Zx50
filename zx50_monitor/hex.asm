; =============================================================================
; Subroutine: ParseHexWord
; Purpose:    Parses an ASCII hex string into a 16-bit binary value.
;             Skips leading spaces. Stops on comma, space, or null.
; Input:      HL = Pointer to the ASCII string buffer
; Output:     DE = Parsed 16-bit value
;             HL = Pointer to the character that stopped the parsing (e.g. ',' or 0x00)
;             Carry (C) Flag = SET if invalid hex character found, RESET if success
; Destroys:   A, DE
; =============================================================================
ParseHexWord:
    LD DE, 0x0000       ; Initialize our 16-bit result accumulator to 0

.skip_spaces:
    LD A, (HL)
    CP ' '
    JR NZ, .parse_loop  ; If it's not a space, start parsing
    INC HL
    JR .skip_spaces

.parse_loop:
    LD A, (HL)          ; Read the next character

    ; 1. Check for valid delimiters (End of string, Comma, or Space)
    OR A                ; Is it Null (0x00)?
    JR Z, .success
    CP ','              ; Is it a Comma?
    JR Z, .success
    CP ' '              ; Is it a Space?
    JR Z, .success

    ; 2. Convert ASCII to Hex Nibble (0x00 - 0x0F)
    SUB '0'             ; ASCII '0' is 0x30. 
    JR C, .error        ; If result < 0, it was an invalid character

    CP 10               
    JR C, .shift_in     ; If result is 0-9, we have our nibble! Jump to shift.

    SUB 7               ; Adjust for 'A'-'F' (ASCII 'A' is 0x41. 0x41 - 0x30 - 7 = 0x0A)
    CP 10               
    JR C, .error        ; If it's between '9' and 'A', invalid character.
    
    CP 16               
    JR C, .shift_in     ; If result is 10-15, we have an uppercase 'A'-'F' nibble!

    SUB 32              ; Adjust for 'a'-'f' (ASCII 'a' is 0x61)
    CP 10
    JR C, .error        ; If it's between 'F' and 'a', invalid character.
    
    CP 16
    JR NC, .error       ; If result is > 15, it's past 'f', invalid character.

.shift_in:
    ; 3. Shift the DE accumulator left by 4 bits to make room for the new nibble
    PUSH HL             ; Save our string pointer
    EX DE, HL           ; Swap DE into HL (because Z80 can only do 16-bit ADDs with HL)
    ADD HL, HL          ; x2
    ADD HL, HL          ; x4
    ADD HL, HL          ; x8
    ADD HL, HL          ; x16 (Shifted left 4 bits)
    EX DE, HL           ; Swap the shifted value back into DE
    POP HL              ; Restore our string pointer

    ; 4. Insert the new nibble into the bottom of DE
    OR E                ; A holds our new nibble. OR it with the bottom byte of DE.
    LD E, A             ; Store it back in E.

    INC HL              ; Advance the string pointer to the next character
    JR .parse_loop      ; Keep going!

.success:
    OR A                ; Clear the Carry Flag to signal success
    RET

.error:
    SCF                 ; Set the Carry Flag to signal an error
    RET

; =============================================================================
; Subroutine: PrintHexWord
; Purpose:    Prints a 16-bit value as four ASCII Hex characters
; Input:      HL = 16-bit value to print
; Destroys:   None (Registers are preserved)
; =============================================================================
PrintHexWord:
    PUSH AF
    LD A, H                 ; Load the upper byte
    CALL PrintHexByte       ; Print it
    LD A, L                 ; Load the lower byte
    CALL PrintHexByte       ; Print it
    POP AF
    RET

; =============================================================================
; Subroutine: PrintHexByte
; Purpose:    Prints an 8-bit value as two ASCII Hex characters
; Input:      A = 8-bit value to print
; Destroys:   None (Registers are preserved)
; =============================================================================
PrintHexByte:
    PUSH AF                 ; Save the original byte
    RRCA                    ; Rotate the upper 4 bits into the lower 4 bits
    RRCA
    RRCA
    RRCA
    CALL PrintHexNibble     ; Convert and print the upper nibble
    POP AF                  ; Restore the original byte
    CALL PrintHexNibble     ; Convert and print the lower nibble
    RET

; =============================================================================
; Subroutine: PrintHexNibble
; Purpose:    Converts the lower 4 bits of A into an ASCII char and prints it
; Input:      A = Value containing the nibble in the lower 4 bits
; Destroys:   None (Registers are preserved)
; =============================================================================
PrintHexNibble:
    PUSH AF                 ; Save A so we don't destroy it for the caller
    AND 0x0F                ; Mask out the upper 4 bits (we only want 0x00-0x0F)
    
    CP 10                   ; Is it 0-9?
    JR C, .is_digit         ; If so, jump to digit formatting
    
    ; If we get here, it is A-F (10-15)
    ADD A, 'A' - 10         ; Add the ASCII offset for 'A' (0x41 - 10 = 55)
    JR .print
    
.is_digit:
    ADD A, '0'              ; Add the ASCII offset for '0' (0x30)
    
.print:
    CALL Console_Tx         ; Print the ASCII character
    POP AF                  ; Restore the original A
    RET

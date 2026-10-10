; ==============================================================================
; DIV_I64: 64-bit signed integer division: A / B
;
; Inputs:
;   Stack: TOS = 64-bit integer B (divisor), NOS = 64-bit integer A (dividend)
;
; Outputs:
;   Stack: TOS = quotient (A / B) truncated toward zero
;   Status flags:
;     ERR and OVERFLOW set if B == 0 (division by zero, aborts without pushing)
;     OVERFLOW set if A == -2^63 and B == -1 (result overflows 64-bit signed int)
;     Updated by final operation (ZERO, SIGN)
;     or set on underflow if stack < 4 words (16 bytes).
;
; Register Allocation:
;   AX (AL, AH) : Dividend A (NOS) / Quotient Q (A / B)
;   BX (BL, BH) : Divisor B (TOS) / |B|
;   CX (CL, CH) : Remainder R
;   DL          : Sign tracker (DL[31] = sign(A) ^ sign(B))
;   FX (FL, FH) : Scratch register
;   C           : Loop counter (64 iterations)
;
; Subroutines Called:
;   POP_TWO_64
; ==============================================================================

USER_DIV_I64:
    CALL POP_TWO_64             ; AX <- A (NOS), BX <- B (TOS)
    OR.64 BX, BX                ; Test if divisor B == 0
    JZ ZERO, DIV_I64_DIV_ZERO   ; If B == 0, abort with divide-by-zero

    ; Compute expected result sign: DL[31] = AH[31] ^ BH[31]
    MOV DL, AH
    XOR DL, BH

    ; Take |A|: if A < 0, AX = 0 - AX
    OR.64 AX, AX
    JZ SIGN, DIV_I64_A_POS
    XOR.64 FX, FX
    SUB.64 AX, FX, AX
DIV_I64_A_POS:

    ; Take |B|: if B < 0, BX = 0 - BX
    OR.64 BX, BX
    JZ SIGN, DIV_I64_B_POS
    XOR.64 FX, FX
    SUB.64 BX, FX, BX
DIV_I64_B_POS:

    ; Initialize remainder R = 0 in CX
    XOR.64 CX, CX

    ; Set loop counter C = 64 iterations
    LDI C, 64

DIV_I64_LOOP:
    LSL.64 AX, 1                ; Q << 1, CARRY = old Q[63]
    JNZ CARRY, DIV_I64_Q_CARRY

    ; Path 1: Q[63] was 0
    LSL.64 CX, 1                ; R << 1
    SUB.64 CX, CX, BX           ; R = R - D
    JNZ CARRY, DIV_I64_RESTORE1
    OR AL, 1                    ; R >= D: set Q[0] = 1
    DJNZ DIV_I64_LOOP
    JMP DIV_I64_LOOP_DONE
DIV_I64_RESTORE1:
    ADD.64 CX, CX, BX           ; R < D: restore R = R + D
    DJNZ DIV_I64_LOOP
    JMP DIV_I64_LOOP_DONE

DIV_I64_Q_CARRY:
    ; Path 2: Q[63] was 1
    LSL.64 CX, 1                ; R << 1
    OR CL, 1                    ; R = (R << 1) | 1
    SUB.64 CX, CX, BX           ; R = R - D
    JNZ CARRY, DIV_I64_RESTORE2
    OR AL, 1                    ; R >= D: set Q[0] = 1
    DJNZ DIV_I64_LOOP
    JMP DIV_I64_LOOP_DONE
DIV_I64_RESTORE2:
    ADD.64 CX, CX, BX           ; R < D: restore R = R + D
    DJNZ DIV_I64_LOOP

DIV_I64_LOOP_DONE:
    ; Check expected sign in DL[31]
    OR DL, DL
    JNZ SIGN, DIV_I64_NEGATE

    ; Expected positive result:
    ; Check for signed overflow (-2^63 / -1):
    ; If positive expected but bit 63 is set, overflow occurred!
    OR.64 AX, AX
    JZ SIGN, DIV_I64_PUSH_POS
    PUSH AX                     ; Push 64-bit quotient {AH, AL}
    LDI OVERFLOW, 1             ; Set OVERFLOW flag on (-2^63) / (-1) AFTER PUSH
    HALT

DIV_I64_PUSH_POS:
    PUSH AX                     ; Push 64-bit quotient {AH, AL}
    HALT

DIV_I64_NEGATE:
    ; Result should be negative: AX = 0 - AX
    XOR.64 FX, FX
    SUB.64 AX, FX, AX
    PUSH AX                     ; Push 64-bit quotient {AH, AL}
    HALT

DIV_I64_DIV_ZERO:
    LDI ERR, 1
    LDI OVERFLOW, 1
    HALT

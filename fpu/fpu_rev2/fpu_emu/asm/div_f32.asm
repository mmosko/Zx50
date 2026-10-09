; ==============================================================================
; DIV_F32: IEEE-754 Single-Precision Division: A / B
;
; Inputs:
;   Stack: TOS = float32 B (divisor), NOS = float32 A (dividend)
;
; Outputs:
;   Stack: TOS = float32 (A / B)
;   Status flags:
;     ERR set if B == 0 (division by zero, triggered via DIVU AL, 0)
;     Updated by NORMALIZE_F32 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Dividend mantissa / iterative quotient chunk / normalized float result
;   AH : 24-bit quotient accumulator Q_24 / sign carrier into NORMALIZE_F32 (AH[31])
;   BL : Divisor mantissa
;   BH : Sign tracker: BH[31] = sign(A) ^ sign(B) (preserved across DIVU)
;   EA : Exponent of A / result exponent (EA - EB + 126)
;   EB : Exponent of B
;   C  : Loop counter for 8-bit iterative division steps (2 iterations)
;   DL : Remainder register written by hardware divider DIVU
;   F  : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32, NORMALIZE_F32
; ==============================================================================

USER_DIV_F32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    CALL DIV_F32_CORE           ; AL <- A / B
    JNZ ERR, DIV_F32_HALT       ; If divide-by-zero (ERR set), abort without pushing
    PUSH AL                     ; Push result
DIV_F32_HALT:
    HALT

DIV_F32_CORE:
    MOV BH, AL                  ; Stash A in BH
    XOR BH, BL                  ; BH[31] = s_A ^ s_B (result sign)
    UNPACK BL, EB               ; Unpack divisor B: EB <- exp_B, BL <- mant_B
    JZ ZERO, DIV_F32_DIV_ZERO   ; If B == 0: trigger divide-by-zero
    UNPACK AL, EA               ; Unpack dividend A: EA <- exp_A, AL <- mant_A
    JZ ZERO, DIV_F32_ZERO       ; If A == 0: return zero with computed sign
    EXP_SUB EA, EB              ; EA <- exp_A - exp_B
    EXP_ADD EA, 126             ; EA <- exp_A - exp_B + 126 (re-bias for 24-bit quotient)
    LSL AL, 8                   ; Initial dividend shift: AL << 8
    DIVU AL, BL                 ; AL <- q0, DL <- r0
    MOV AH, AL                  ; AH <- q0
    LDI C, 2                    ; 2 more iterations of 8-bit quotient generation
DIV_LOOP:
    MOV AL, DL                  ; AL <- remainder from DIVU
    LSL AL, 8                   ; AL <- r << 8
    DIVU AL, BL                 ; AL <- q_i, DL <- r_i
    LSL AH, 8                   ; Shift accumulated quotient: AH << 8
    OR AH, AL                   ; AH <- (q << 8) | q_i
    DJNZ DIV_LOOP               ; Repeat for 24-bit total quotient

    MOV AL, AH                  ; AL <- 24-bit quotient mantissa
    MOV AH, BH                  ; AH[31] <- result sign for NORMALIZE_F32
DIV_F32_NORM:
    CALL NORMALIZE_F32          ; Normalize mantissa in AL, exponent in EA, sign in AH[31]
    RET

DIV_F32_ZERO:
    XOR AL, AL                  ; Return zero mantissa
    MOV AH, BH                  ; Preserve computed sign
    JMP DIV_F32_NORM

DIV_F32_DIV_ZERO:
    XOR BL, BL                  ; BL <- 0
    DIVU AL, BL                 ; Force hardware divide-by-zero error (sets ERR flag)
    RET

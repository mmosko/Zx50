; ==============================================================================
; MUL_F32: IEEE-754 Single-Precision Multiplication: A * B
;
; Inputs:
;   Stack: TOS = float32 B, NOS = float32 A
;
; Outputs:
;   Stack: TOS = float32 (A * B)
;   Status flags:
;     Updated by NORMALIZE_F32 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A mantissa / product low word / normalized float result
;   AH : Product high word / packed sign carrier into NORMALIZE_F32 (AH[31])
;   BL : Operand B mantissa
;   BH : Sign tracker: BH[31] = sign(A) ^ sign(B) (preserved across MULU)
;   EA : Exponent of A / product exponent (EA + EB - 127)
;   EB : Exponent of B
;   D, F : Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32, NORMALIZE_F32
; ==============================================================================

USER_MUL_F32:
    CALL POP_TWO_32             ; AL <- A (NOS), BL <- B (TOS)
    CALL MUL_F32_CORE           ; AL <- A * B
    PUSH AL
    HALT

MUL_F32_CORE:
    MOV BH, AL                  ; Stash A into BH
    XOR BH, BL                  ; BH[31] = s_A ^ s_B (result sign)
    UNPACK BL, EB               ; Unpack B: EB <- exp_B, BL <- mant_B
    JZ ZERO, MUL_F32_ZERO       ; If B == 0: return zero with computed sign
    UNPACK AL, EA               ; Unpack A: EA <- exp_A, AL <- mant_A
    JZ ZERO, MUL_F32_ZERO       ; If A == 0: return zero with computed sign
    EXP_ADD EA, EB              ; EA <- exp_A + exp_B
    EXP_SUB EA, 127             ; EA <- exp_A + exp_B - 127 (re-bias)
    MULU AL, BL                 ; {AH, AL} <- mant_A * mant_B (unsigned 48-bit product)
    LSR AX, 23                  ; Align 48-bit product: mantissa into AL[24:0]
    MOV AH, BH                  ; AH[31] <- result sign for NORMALIZE_F32
MUL_F32_NORM:
    CALL NORMALIZE_F32          ; Normalize mantissa in AL, exponent in EA, sign in AH[31]
    RET
MUL_F32_ZERO:
    XOR AL, AL                  ; Return zero mantissa
    MOV AH, BH                  ; Preserve computed sign
    JMP MUL_F32_NORM

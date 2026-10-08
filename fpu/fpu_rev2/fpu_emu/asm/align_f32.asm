; ==============================================================================
; ALIGN_F32: Subroutine to align exponents of two unpacked float32 operands
;
; Inputs:
;   AL : Mantissa of operand A
;   BL : Mantissa of operand B
;   EA : Exponent of operand A
;   EB : Exponent of operand B
;   AH : Packed float A (for sign tracking in bit 31)
;   DL : Packed float B (for sign tracking in bit 31)
;
; Outputs:
;   AL : Mantissa of larger operand
;   BL : Mantissa of smaller operand, preshifted right by (EA - EB)
;   EA : Exponent of larger operand
;   EB : Exponent of smaller operand
;   AH : Packed float of larger operand (AH[31] holds result sign)
;   C  : Exponent difference (EA - EB)
;   Status flags:
;     DIFF_SIGN (DF) is preserved from UNPACK
;
; Returns via RET.
; ==============================================================================

ALIGN_F32:
    CMP EA, EB
    JNZ CARRY, ALIGN_F32_SWAP        ; (SWAP_OPS: EA < EB)
    JNZ ZERO, ALIGN_F32_EXP          ; (ALIGN_EXP: EA > EB)
    CMP AL, BL
    JZ CARRY, ALIGN_F32_EXP          ; (ALIGN_EXP: AL >= BL)
ALIGN_F32_SWAP:
    SWAP AL, BL                     ; (larger mantissa in AL)
    SWAP EA, EB                     ; (larger exponent in EA)
    MOV AH, DL                      ; (AH now holds packed larger operand)
ALIGN_F32_EXP:
    EXP_SUB C, EA, EB               ; (C <- EA - EB; EA preserved!)
    CMP C, 32
    JNZ CARRY, ALIGN_F32_SHIFT       ; (DO_SHIFT: diff < 32)
    MOV BL, 0                       ; (diff >= 32: smaller mantissa shifts to 0)
    RET
ALIGN_F32_SHIFT:
    LSR BL, C                       ; (shift BL right by C)
    RET

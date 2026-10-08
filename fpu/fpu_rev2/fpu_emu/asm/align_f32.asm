; ==============================================================================
; ALIGN_F32: Subroutine to align exponents of two unpacked float32 operands
;
; Inputs:
;   AL : Mantissa of operand A
;   BL : Mantissa of operand B
;   EA : Exponent of operand A
;   EB : Exponent of operand B
;   AH : Packed float A (for sign tracking in bit 31)
;   FL : (Clobbered by hardware SWAP as intermediary)
;   FH : Packed float B (scratch copy for sign tracking in bit 31)
;
; Outputs:
;   AL : Mantissa of larger operand
;   BL : Mantissa of smaller operand, preshifted right by (EA - EB)
;   EA : Exponent of larger operand
;   EB : Exponent of smaller operand
;   AH : Packed float of larger operand (AH[31] holds result sign)
;   FH : Packed float B (preserved)
;   C  : Exponent difference (EA - EB)
;   Status flags:
;     DIFF_SIGN (DF) is preserved from UNPACK
;
; Scratch & Preserved:
;   FL : Hardware intermediary used during SWAP
;   FH : Software scratch holding packed B
;   D  : (DL, DH) Untouched / preserved
;
; Returns via RET.
; ==============================================================================

ALIGN_F32:
    CMP EA, EB
    JNZ CARRY, ALIGN_F32_SWAP        ; EA < EB: swap operands so larger is in A
    JNZ ZERO, ALIGN_F32_EXP          ; EA > EB: A is already larger
    CMP AL, BL
    JZ CARRY, ALIGN_F32_EXP          ; EA == EB, AL >= BL: A is larger
ALIGN_F32_SWAP:
    SWAP AL, BL                     ; Larger mantissa into AL (uses FL as hardware intermediary)
    SWAP EA, EB                     ; Larger exponent into EA (uses FL as hardware intermediary)
    MOV AH, FH                      ; AH now holds packed larger operand (sign)
ALIGN_F32_EXP:
    EXP_SUB C, EA, EB               ; C <- EA - EB (exponent difference)
    CMP C, 32
    JNZ CARRY, ALIGN_F32_SHIFT       ; If diff < 32, perform shift
    MOV BL, 0                       ; If diff >= 32, smaller mantissa underflows to 0
    RET
ALIGN_F32_SHIFT:
    LSR BL, C                       ; Align smaller mantissa: BL >>= (EA - EB)
    RET

; ==============================================================================
; ADD_F32: IEEE-754 Single-Precision Addition
;
; Inputs:
;   Stack: TOS = float32 B, NOS = float32 A
;
; Outputs:
;   Stack: TOS = float32 (A + B)
;   Status flags:
;     Updated by NORMALIZE_F32 (ZERO, SIGN, OVERFLOW, UNDERFLOW, INEXACT)
;     or set on underflow if stack < 2 words.
;
; Register Allocation:
;   AL : Operand A mantissa / final result packed float
;   AH : Stashed packed A (AH[31] = sign of result)
;   BL : Operand B mantissa
;   EA : Exponent of A / final exponent
;   EB : Exponent of B
;   FH : Scratch register holding packed B (for sign tracking and return-B)
;   FL : Hardware intermediary clobbered by SWAP in ALIGN_F32
;   C  : Exponent difference computed by ALIGN_F32
;   D  : (DL, DH) Preserved / untouched
;
; Subroutines Called:
;   POP_TWO_32, ALIGN_F32, NORMALIZE_F32
; ==============================================================================

USER_ADD_F32:
    CALL POP_TWO_32
ADD_F32_CORE:
    MOV FH, BL                  ; Scratch FH <- packed B (preserves sign and value)
    MOV AH, AL                  ; AH <- packed A (preserves sign of A in bit 31)
    UNPACK BL, EB               ; Unpack B: EB <- exp_B, BL <- mant_B
    JZ ZERO, ADD_F32_RETURN_A   ; If B == 0: return A
    UNPACK AL, EA               ; Unpack A: EA <- exp_A, AL <- mant_A
    JZ ZERO, ADD_F32_RETURN_B   ; If A == 0: return B
    CALL ALIGN_F32              ; Align exponents: larger in AL/EA, smaller in BL/EB
    JNZ DIFF_SIGN, ADD_F32_SUB  ; If signs differ: subtract mantissas
    ADD AL, BL                  ; Same sign: add mantissas
    JMP ADD_F32_NORM
ADD_F32_SUB:
    SUB AL, BL                  ; Different signs: subtract smaller mantissa from larger
ADD_F32_NORM:
    CALL NORMALIZE_F32          ; Normalize mantissa in AL with exponent in EA, sign in AH[31]
ADD_F32_RETURN_A:
    PUSH AL                     ; Push result (or original A if B == 0)
    HALT
ADD_F32_RETURN_B:
    PUSH FH                     ; Push original B (from scratch register FH)
    HALT

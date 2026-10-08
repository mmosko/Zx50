; =========================
; MUL_F32
; =========================

USER_MUL_F32:
    CALL POP_TWO_32
    MOV BH, AL                      ; stash A into BH
    XOR BH, BL                      ; BH[31] = s_A ^ s_B, preserved across MULU and shifts
    UNPACK BL, EB                   ; unpack B: EB <- exp_B, BL <- mant_B
    JZ ZERO, MUL_F32_24             ; RETURN_ZERO
    UNPACK AL, EA                   ; unpack A: EA <- exp_A, AL <- mant_A
    JZ ZERO, MUL_F32_24             ; RETURN_ZERO
    EXP_ADD EA, EB                  ; EA <- EA + EB
    EXP_SUB EA, 127                 ; EA <- EA - 127
    MULU AL, BL                     ; {AH, AL} <- AL * BL unsigned 48-bit product
    LSR AX, 23                      ; {AH, AL} >>= 23, mantissa in AL[24:0]
    LZC AL                          ; C <- leading zero count of AL
    CMP C, 8                        ; compare C with 8: 7 if bit 24 set, 8 if bit 23 set
    JNZ CARRY, MUL_F32_18           ; OVERFLOW_RIGHT: C < 8
    JMP MUL_F32_20                  ; DONE_NORM
MUL_F32_18:
    LSR AL, 1                       ; AL >>= 1
    EXP_ADD EA, 1                   ; EA += 1
MUL_F32_20:
    OR BH, BH                       ; restores status.sign from BH[31]
    PACK AL, EA                     ; packs float32 into AL
    PUSH AL
    HALT
MUL_F32_24:
    XOR AL, AL                      ; RETURN_ZERO: AL <- 0
    JMP MUL_F32_20                  ; DONE_NORM -> OR BH, BH -> PACK -> PUSH -> HALT

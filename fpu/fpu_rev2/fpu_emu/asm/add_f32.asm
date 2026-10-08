; ==============================================================================
; ADD_F32: IEEE-754 Single-Precision Addition
; ==============================================================================

USER_ADD_F32:
    CALL POP_TWO_32
ADD_F32_CORE:
    MOV DL, BL                  ; stash packed B into DL
    MOV AH, AL                  ; stash packed A into AH for sign preservation
    UNPACK BL, EB
    JZ ZERO, ADD_F32_RETURN_A   ; (RETURN_A: jump to PUSH AL, HALT)
    UNPACK AL, EA
    JZ ZERO, ADD_F32_RETURN_B   ; (RETURN_B: jump to PUSH DL, HALT)
    CALL ALIGN_F32
    JNZ DIFF_SIGN, ADD_F32_SUB  ; (DO_SUB)
    ADD AL, BL
    JMP ADD_F32_NORM
ADD_F32_SUB:
    SUB AL, BL
ADD_F32_NORM:
    CALL NORMALIZE_F32
ADD_F32_RETURN_A:
    PUSH AL
    HALT
ADD_F32_RETURN_B:
    PUSH DL                     ; RETURN_B
    HALT

from fpu_asm.assembler import Assembler


def main():
    sample_program = """
        .org 0x000
    start:
        ADD AL, BL          ; 2-operand 32-bit addition
        ADD AX, BX, DL      ; 3-operand 64-bit addition
        LDC AL, CONST, 0x02 ; Load pi constant
        JNZ ERR, start      ; Conditional jump on error
        HALT
    """

    assembler = Assembler()
    program = assembler.assemble(sample_program)

    print(f"--- Assembled {len(program)} Micro-Instructions ---\n")
    for addr, uinst in program.items():
        print(f"  [0x{addr:03X}] {uinst}")


if __name__ == "__main__":
    main()

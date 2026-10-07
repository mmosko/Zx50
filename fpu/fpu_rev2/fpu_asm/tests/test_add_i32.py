from fpu_asm.assembler import Assembler
from fpu_emu.micro_code import MicroCode
from fpu_emu.user_opcodes import UserOpcode


# ADD_I32:
# 0: POP BL
# 1: JNZ UNDERFLOW -> 6 (HALT)
# 2: POP AL
# 3: JNZ UNDERFLOW -> 6 (HALT)
# 4: ADD AL, BL
# 5: PUSH AL
# 6: HALT

def test_equ_and_align_directives():
    code = """
    ADD_I32:
        POP BL
        JNZ UF, ADD_I32_HALT
        POP AL
        JNZ UF, ADD_I32_HALT
        ADD AL, BL
        PUSH AL
    ADD_I32_HALT:
        HALT
    """
    assembler = Assembler()
    prog = assembler.assemble(code)

    expected = MicroCode.get(UserOpcode.ADD_I32)
    assert [u for _, u in prog] == expected
    assert [addr for addr, _ in prog] == list(range(len(expected)))

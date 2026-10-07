from pathlib import Path
from typing import Dict, Tuple, Optional
from lark import Lark, Visitor, Transformer, Token, Tree

from fpu_emu.hardware.reg import Reg
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.micro_instruction import MicroInstruction, IW


FLAG_MAP = {
    "BSY": 7,
    "ZF": 6, "Z": 6,
    "SF": 5, "S": 5,
    "CF": 4, "C": 4,
    "VF": 3, "V": 3,
    "UF": 2, "U": 2,
    "ERR": 1,
    "DIFF_SIGN": 0, "D": 0,
}


class Pass1SymbolCollector(Visitor):
    """Pass 1: Scans the AST to build the symbol table and calculate microcode addresses."""

    def __init__(self):
        self.symbols: Dict[str, int] = {}
        self.current_address: int = 0

    def dir_org(self, tree: Tree):
        imm_token = tree.children[0].children[0]
        self.current_address = self._parse_int(imm_token)

    def dir_equ(self, tree: Tree):
        name = str(tree.children[0].value)
        imm_token = tree.children[1].children[0]
        self.symbols[name] = self._parse_int(imm_token)

    def label(self, tree: Tree):
        label_name = str(tree.children[0].value)
        self.symbols[label_name] = self.current_address

    def instruction(self, tree: Tree):
        self.current_address += 1

    def _parse_int(self, token: Token) -> int:
        if token.type == "HEX_INT":
            return int(token.value, 16)
        elif token.type == "BIN_INT":
            return int(token.value, 2)
        return int(token.value, 10)


class Pass2Encoder(Transformer):
    """Pass 2: Converts AST nodes into (address, MicroInstruction) tuples."""

    def __init__(self, symbol_table: Dict[str, int]):
        super().__init__()
        self.symbols = symbol_table
        self.current_address = 0

    def HEX_INT(self, token):
        return int(token.value, 16)

    def BIN_INT(self, token):
        return int(token.value, 2)

    def INT(self, token):
        return int(token.value, 10)

    def CNAME(self, token):
        name = str(token.value)
        if name in self.symbols:
            return self.symbols[name]
        raise KeyError(f"Undefined symbol: '{name}'")

    def FLAG(self, token):
        flag_str = str(token.value).upper()
        return FLAG_MAP.get(flag_str, 0)

    def TABLE(self, token):
        return str(token.value).upper()

    def reg(self, children):
        reg_name = str(children[0].value).upper()
        return Reg[reg_name]

    def imm_operand(self, children):
        return children[0]

    def reg_or_imm(self, children):
        return children[0]

    def dir_org(self, children):
        self.current_address = children[0]
        return None

    def dir_equ(self, children):
        return None

    def statement(self, children):
        return children[0]

    def line(self, children):
        for item in children:
            if isinstance(item, tuple) and isinstance(item[1], MicroInstruction):
                return item
        return None

    def start(self, children):
        return {addr: uinst for item in children if item is not None for addr, uinst in [item]}

    def instruction(self, children):
        uinst = children[0]
        addr = self.current_address
        self.current_address += 1
        return (addr, uinst)

    # -------------------------------------------------------------------------
    # Instruction Constructors
    # -------------------------------------------------------------------------

    def inst_arith(self, children):
        op_str = str(children[0].value).upper()
        dst = children[1]

        if len(children) == 4:
            src1 = children[2]
            src2 = children[3]
        else:
            src1 = dst
            src2 = children[2]

        is_64 = dst.name.endswith("X")
        w = IW.W64 if is_64 else IW.W32

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            imm=src2 if isinstance(src2, int) else 0,
        )

    def inst_cmp(self, children):
        src1, src2 = children[0], children[1]
        is_64 = (isinstance(src1, Reg) and src1.name.endswith("X")) or (
            isinstance(src2, Reg) and src2.name.endswith("X")
        )
        w = IW.W64 if is_64 else IW.W32

        return MicroInstruction(
            op=MicroOp.CMP,
            w=w,
            dst=Reg.NONE,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            imm=src2 if isinstance(src2, int) else 0,
        )

    def inst_math(self, children):
        op_str = str(children[0].value).upper()
        dst = children[1]
        src2 = children[2]

        is_64 = dst.name.endswith("X")
        w = IW.W64 if is_64 else IW.W32

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src=dst,
            imm=src2 if isinstance(src2, int) else 0,
        )

    def inst_logic(self, children):
        op_str = str(children[0].value).upper()
        dst = children[1]

        is_64 = dst.name.endswith("X")
        w = IW.W64 if is_64 else IW.W32

        if len(children) == 2:  # FABS, FCHS, NOT
            return MicroInstruction(op=MicroOp.parse(op_str), w=w, dst=dst, src=dst)

        if len(children) == 4:
            src1, src2 = children[2], children[3]
        else:
            src1, src2 = dst, children[2]

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            flag=None,
            imm=src2 if isinstance(src2, int) else 0,
        )

    def inst_ctrl(self, children):
        op_token = children[0]
        op_str = str(op_token.value if isinstance(op_token, Token) else op_token).upper()

        flag_cond = 0
        imm_val = 0

        for child in children[1:]:
            if isinstance(child, int):
                # Could be flag_cond or imm address
                if flag_cond == 0 and child < 8:
                    flag_cond = child
                else:
                    imm_val = child

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=IW.W32,
            dst=Reg.NONE,
            src1=Reg.NONE,
            src=Reg.NONE,
            flag=flag_cond,
            imm=imm_val,
        )


class Assembler:
    """Facade for loading ucode.lark and driving Pass 1 + Pass 2 assembly."""

    def __init__(self, grammar_path: Optional[Path] = None):
        if grammar_path is None:
            grammar_path = Path(__file__).parent / "ucode.lark"

        with open(grammar_path, "r") as f:
            self.parser = Lark(f.read(), parser="earley")

    def assemble(self, source_code: str) -> Dict[int, MicroInstruction]:
        # Parse into Lark AST
        tree = self.parser.parse(source_code)

        # Pass 1: Collect symbols & addresses
        collector = Pass1SymbolCollector()
        collector.visit(tree)

        # Pass 2: Encode instructions
        encoder = Pass2Encoder(collector.symbols)
        program_image = encoder.transform(tree)

        return program_image

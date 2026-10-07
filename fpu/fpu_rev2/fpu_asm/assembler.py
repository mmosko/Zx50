from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from lark import Lark, Visitor, Transformer, Token, Tree

from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import StatusFlag
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.rom.fpu_const_map import FpuTable, FpuConst, FpuCheb


FLAG_MAP = {
    "DIFF_SIGN": StatusFlag.DIFF_SIGN.value,
    "DF": StatusFlag.DIFF_SIGN.value,
    "D": StatusFlag.DIFF_SIGN.value,
    "ERR": StatusFlag.ERR.value,
    "EF": StatusFlag.ERR.value,
    "UNDERFLOW": StatusFlag.UNDERFLOW.value,
    "UF": StatusFlag.UNDERFLOW.value,
    "U": StatusFlag.UNDERFLOW.value,
    "OVERFLOW": StatusFlag.OVERFLOW.value,
    "VF": StatusFlag.OVERFLOW.value,
    "V": StatusFlag.OVERFLOW.value,
    "CARRY": StatusFlag.CARRY.value,
    "CF": StatusFlag.CARRY.value,
    "C": StatusFlag.CARRY.value,
    "SIGN": StatusFlag.SIGN.value,
    "SF": StatusFlag.SIGN.value,
    "S": StatusFlag.SIGN.value,
    "ZERO": StatusFlag.ZERO.value,
    "ZF": StatusFlag.ZERO.value,
    "Z": StatusFlag.ZERO.value,
    "BUSY": StatusFlag.BUSY.value,
    "BF": StatusFlag.BUSY.value,
    "BSY": StatusFlag.BUSY.value,
}

TABLE_MAP = {
    "RECIP": FpuTable.RECIP,
    "SQRT": FpuTable.SQRT,
    "TRIG": FpuTable.TRIG,
    "CHEB": FpuTable.CHEB,
    "CONST": FpuTable.CONST,
}


class Pass1SymbolCollector(Visitor):
    """Pass 1: Scans the AST to build the symbol table and calculate microcode addresses."""

    def __init__(self):
        self.symbols: Dict[str, int] = {}
        self.current_address: int = 0

    def dir_org(self, tree: Tree):
        token = tree.children[0].children[-1]
        self.current_address = self._parse_int(token)

    def dir_equ(self, tree: Tree):
        name = str(tree.children[0].value)
        token = tree.children[1].children[-1]
        self.symbols[name] = self._parse_int(token)

    def dir_align(self, tree: Tree):
        token = tree.children[0].children[-1]
        n = self._parse_int(token)
        if n > 0 and self.current_address % n != 0:
            self.current_address = ((self.current_address + n - 1) // n) * n

    def label(self, tree: Tree):
        name = str(tree.children[0].value)
        self.symbols[name] = self.current_address

    def instruction(self, _tree: Tree):
        self.current_address += 1

    def _parse_int(self, token: Token) -> int:
        val = str(token.value).lstrip("#")
        if val in self.symbols:
            return self.symbols[val]
        if val.upper() in FLAG_MAP:
            return FLAG_MAP[val.upper()]
        return int(val, 0)


class Pass2Encoder(Transformer):
    """Pass 2: Converts AST nodes into (address, MicroInstruction) tuples."""

    def __init__(self, symbol_table: Dict[str, int]):
        super().__init__()
        self.symbols = symbol_table
        self.current_address = 0

    def HEX_INT(self, token: Union[str | Tree]):
        return int(token.value, 16)

    def BIN_INT(self, token: Union[str | Tree]):
        return int(token.value, 2)

    def SIGNED_INT(self, token):
        return int(token.value, 10)

    def SYMBOL(self, token):
        name = str(token.value)
        if name in self.symbols:
            return self.symbols[name]
        if name.upper() in TABLE_MAP:
            return TABLE_MAP[name.upper()]
        if name.upper() in FLAG_MAP:
            return FLAG_MAP[name.upper()]
        if hasattr(FpuConst, name):
            return getattr(FpuConst, name).value
        if hasattr(FpuCheb, name):
            return getattr(FpuCheb, name).value
        raise KeyError(f"Undefined symbol: '{name}'")

    def FLAG(self, token):
        return FLAG_MAP.get(str(token.value).upper(), 0)

    def TABLE_NAME(self, token):
        return TABLE_MAP.get(str(token.value).upper(), 0)

    def WIDTH_SUFFIX(self, token):
        return str(token.value)

    def COMMENT(self, _token):
        return None

    def comment(self, _children):
        return None

    def label(self, _children):
        return None

    def reg(self, children):
        return Reg[str(children[0].value).upper()]

    def reg_or_imm(self, children):
        return children[0]

    def imm_operand(self, children):
        return children[-1]

    def table_ref(self, children):
        return children[0]

    def dir_org(self, children):
        self.current_address = children[0]
        return None

    def dir_equ(self, _children):
        return None

    def dir_subroutine(self, _children):
        return None

    def dir_align(self, children):
        n = children[0]
        if n > 0 and self.current_address % n != 0:
            self.current_address = ((self.current_address + n - 1) // n) * n
        return None

    def dir_entry(self, _children):
        return None

    def dir_global(self, _children):
        return None

    def directive(self, _children):
        return None

    def inst_body(self, children):
        return children[0]

    def instruction(self, children):
        uinst = children[-1]
        addr = self.current_address
        self.current_address += 1
        return (addr, uinst)

    def statement(self, children):
        return children[0]

    def line(self, children):
        for item in children:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], MicroInstruction):
                return item
        return None

    def line_eof(self, children):
        return self.line(children)

    def start(self, children):
        return [
            item
            for item in children
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], MicroInstruction)
        ]

    # -------------------------------------------------------------------------
    # Helper Normalizers
    # -------------------------------------------------------------------------

    def _normalize_reg(self, reg: Reg) -> Tuple[Reg, bool]:
        if reg == Reg.AX:
            return Reg.AL, True
        if reg == Reg.BX:
            return Reg.BL, True
        if reg == Reg.DX:
            return Reg.DL, True
        if reg == Reg.FX:
            return Reg.FL, True
        return reg, False

    def _parse_reg_or_imm(self, val: Union[Reg, int]) -> Tuple[Reg, int, bool]:
        if isinstance(val, Reg):
            norm_reg, is_64 = self._normalize_reg(val)
            return norm_reg, 0, is_64
        return Reg.IMM, int(val), False

    # -------------------------------------------------------------------------
    # Instruction Constructors
    # -------------------------------------------------------------------------

    def inst_arith(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1

        dst, is_64_dst = self._normalize_reg(children[idx])
        idx += 1

        rem = len(children) - idx
        if rem == 2:
            src1, is_64_s1 = self._normalize_reg(children[idx])
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        else:
            src1 = Reg.NONE
            is_64_s1 = False
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx])

        w = IW.W64 if (forced_w64 or is_64_dst or is_64_s1 or is_64_s2) else IW.W32

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            imm=imm,
        )

    def inst_cmp(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1

        src1, is_64_s1 = self._normalize_reg(children[idx])
        src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])

        w = IW.W64 if (forced_w64 or is_64_s1 or is_64_s2) else IW.W32

        return MicroInstruction(
            op=MicroOp.CMP,
            w=w,
            dst=src1,
            src=src2,
            imm=imm,
        )

    def inst_pack(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        r1, is_64_r1 = self._normalize_reg(children[idx])
        r2, is_64_r2 = self._normalize_reg(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_r1 or is_64_r2) else IW.W32

        if op_str == "UNPACK":
            if r2 in (Reg.EA, Reg.EB):
                dst, src = r2, r1
            else:
                dst, src = r1, r2
        else:
            dst, src = r1, r2

        return MicroInstruction(op=MicroOp.parse(op_str), w=w, dst=dst, src=src)

    def inst_math_alu(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1

        dst, is_64_dst = self._normalize_reg(children[idx])
        idx += 1

        rem = len(children) - idx
        if rem == 2:
            src1, is_64_s1 = self._normalize_reg(children[idx])
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        else:
            src1 = Reg.NONE
            is_64_s1 = False
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx])

        w = IW.W64 if (forced_w64 or is_64_dst or is_64_s1 or is_64_s2) else IW.W32

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            imm=imm,
        )

    def inst_logic_bin(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1

        dst, is_64_dst = self._normalize_reg(children[idx])
        idx += 1

        rem = len(children) - idx
        if rem == 2:
            src1, is_64_s1 = self._normalize_reg(children[idx])
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        else:
            src1 = Reg.NONE
            is_64_s1 = False
            src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx])

        w = IW.W64 if (forced_w64 or is_64_dst or is_64_s1 or is_64_s2) else IW.W32

        return MicroInstruction(
            op=MicroOp.parse(op_str),
            w=w,
            dst=dst,
            src1=src1 if isinstance(src1, Reg) else Reg.NONE,
            src=src2 if isinstance(src2, Reg) else Reg.NONE,
            imm=imm,
        )

    def inst_logic_unary(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        w = IW.W64 if (forced_w64 or is_64_dst) else IW.W32
        return MicroInstruction(op=MicroOp.parse(op_str), w=w, dst=dst, src1=Reg.NONE, src=Reg.NONE)

    def inst_shift(self, children):
        op_str = str(children[0].value).upper()
        idx = 1
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1

        if op_str == "LZC":
            rem = len(children) - idx
            if rem == 1:
                dst = Reg.C
                src2_raw = children[idx]
            else:
                dst, _ = self._normalize_reg(children[idx])
                src2_raw = children[idx + 1]
            src2, imm, is_64_s2 = self._parse_reg_or_imm(src2_raw)
            w = IW.W64 if (forced_w64 or is_64_s2) else IW.W32
            return MicroInstruction(op=MicroOp.LZC, w=w, dst=dst, src=src2, imm=imm)
        else:
            dst, is_64_dst = self._normalize_reg(children[idx])
            idx += 1
            if idx < len(children):
                src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx])
            else:
                src2, imm, is_64_s2 = Reg.C, 0, False
            w = IW.W64 if (forced_w64 or is_64_dst or is_64_s2) else IW.W32
            return MicroInstruction(op=MicroOp.parse(op_str), w=w, dst=dst, src=src2, imm=imm)

    def inst_push(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx])
        w = IW.W64 if (forced_w64 or is_64_s2) else IW.W32
        return MicroInstruction(op=MicroOp.PUSH, w=w, dst=Reg.NONE, src=src2, imm=imm)

    def inst_pop(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        w = IW.W64 if (forced_w64 or is_64_dst) else IW.W32
        return MicroInstruction(op=MicroOp.POP, w=w, dst=dst)

    def inst_ldc(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        table = children[idx + 1]
        offset = children[idx + 2]
        w = IW.W64 if (forced_w64 or is_64_dst) else IW.W32
        if isinstance(offset, Reg):
            src1, _ = self._normalize_reg(offset)
            imm = 0
        else:
            src1 = Reg.IMM
            imm = int(offset)
        return MicroInstruction(op=MicroOp.LDC, w=w, dst=dst, src=table, src1=src1, imm=imm)

    def inst_ldi_reg(self, children):
        dst, _ = self._normalize_reg(children[0])
        imm = int(children[1])
        return MicroInstruction(op=MicroOp.LDI, w=IW.W32, dst=dst, src=Reg.IMM, imm=imm)

    def inst_ldi_flag(self, children):
        flag = StatusFlag(children[0])
        imm = int(children[1])
        return MicroInstruction(op=MicroOp.LDI, w=IW.W32, dst=Reg.NONE, flag=flag, src=Reg.IMM, imm=imm)

    def inst_ld(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        addr = int(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_dst) else IW.W32
        return MicroInstruction(op=MicroOp.LD, w=w, dst=dst, imm=addr)

    def inst_sto(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        addr = int(children[idx])
        src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_s2) else IW.W32
        return MicroInstruction(
            op=MicroOp.STO,
            w=w,
            dst=Reg.NONE,
            src=src2,
            imm=addr if imm == 0 else imm,
        )

    def inst_ldu(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        addr = int(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_dst) else IW.W32
        return MicroInstruction(op=MicroOp.LDU, w=w, dst=dst, imm=addr)

    def inst_stu(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        addr = int(children[idx])
        src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_s2) else IW.W32
        return MicroInstruction(
            op=MicroOp.STU,
            w=w,
            dst=Reg.NONE,
            src=src2,
            imm=addr if imm == 0 else imm,
        )

    def inst_mov(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        src2, imm, is_64_s2 = self._parse_reg_or_imm(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_dst or is_64_s2) else IW.W32
        return MicroInstruction(op=MicroOp.MOV, w=w, dst=dst, src=src2, imm=imm)

    def inst_swap(self, children):
        idx = 0
        forced_w64 = False
        if idx < len(children) and children[idx] in (".64", ".32"):
            if children[idx] == ".64":
                forced_w64 = True
            idx += 1
        dst, is_64_dst = self._normalize_reg(children[idx])
        src2, is_64_s2 = self._normalize_reg(children[idx + 1])
        w = IW.W64 if (forced_w64 or is_64_dst or is_64_s2) else IW.W32
        return MicroInstruction(op=MicroOp.SWAP, w=w, dst=dst, src=src2)

    def inst_jmp(self, children):
        target = int(children[0])
        return MicroInstruction(
            op=MicroOp.JMP,
            w=IW.W32,
            dst=Reg.NONE,
            src=Reg.NONE,
            imm=target,
        )

    def inst_jnz(self, children):
        if len(children) == 2:
            flag_val = int(children[0])
            target = int(children[1])
        else:
            flag_val = StatusFlag.ZERO.value
            target = int(children[0])
        return MicroInstruction(op=MicroOp.JNZ, w=IW.W32, flag=StatusFlag(flag_val), imm=target)

    def inst_jz(self, children):
        if len(children) == 2:
            flag_val = int(children[0])
            target = int(children[1])
        else:
            flag_val = StatusFlag.ZERO.value
            target = int(children[0])
        return MicroInstruction(op=MicroOp.JZ, w=IW.W32, flag=StatusFlag(flag_val), imm=target)

    def inst_djnz(self, children):
        target = int(children[0])
        return MicroInstruction(
            op=MicroOp.DJNZ,
            w=IW.W32,
            dst=Reg.NONE,
            src=Reg.NONE,
            imm=target,
        )

    def inst_call(self, children):
        target = int(children[0])
        return MicroInstruction(
            op=MicroOp.CALL,
            w=IW.W32,
            dst=Reg.NONE,
            src=Reg.NONE,
            imm=target,
        )

    def inst_noarg(self, children):
        op_str = str(children[0].value).upper()
        return MicroInstruction(op=MicroOp.parse(op_str), w=IW.W32)


class Assembler:
    """Facade for loading ucode.lark and driving Pass 1 + Pass 2 assembly."""

    def __init__(self, grammar_path: Optional[Path] = None):
        if grammar_path is None:
            grammar_path = Path(__file__).parent / "ucode.lark"

        with open(grammar_path, "r") as f:
            self.parser = Lark(f.read(), parser="earley")

    def assemble(self, source_code: str) -> List[Tuple[int, MicroInstruction]]:
        if not source_code.endswith("\n"):
            source_code += "\n"
        # Parse into Lark AST
        tree = self.parser.parse(source_code)

        # Pass 1: Collect symbols & addresses (top-down in source order)
        collector = Pass1SymbolCollector()
        collector.visit_topdown(tree)

        # Pass 2: Encode instructions
        encoder = Pass2Encoder(collector.symbols)
        program_image = encoder.transform(tree)

        # Sort by line number (microcode address)
        return sorted(program_image, key=lambda item: item[0])

    @classmethod
    def strip(cls, input: List[Tuple[int, MicroInstruction]]) -> List[MicroInstruction]:
        return [micro_inst for _, micro_inst in input]

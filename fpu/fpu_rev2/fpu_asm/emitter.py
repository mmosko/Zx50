from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import StatusFlag
from fpu_emu.micro_instruction import MicroInstruction, IW
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuTable


def create_nop_instruction() -> MicroInstruction:
    """Returns a canonical NOP micro-instruction."""
    return MicroInstruction(
        op=MicroOp.NOP,
        w=IW.W32,
        dst=Reg.NONE,
        src=Reg.NONE,
        src1=Reg.NONE,
    )


def pad_instructions(
    instructions: List[Tuple[int, MicroInstruction]],
    total_words: Optional[int] = 512,
    nop: Optional[MicroInstruction] = None,
) -> List[MicroInstruction]:
    """Pads a list of (address, micro_instruction) tuples with NOPs for missing addresses.

    :param instructions: Assembled (address, instruction) pairs.
    :param total_words: Target word size to pad up to (default 512). If None, pads up to
                        (max_addr + 1).
    :param nop: Canonical NOP instruction instance to pad missing slots with.
    :return: Continuous list of MicroInstruction instances from address 0 to (size - 1).
    """
    if nop is None:
        nop = create_nop_instruction()

    max_addr = max((addr for addr, _ in instructions), default=-1)
    target_size = max(total_words or 0, max_addr + 1)

    result: List[MicroInstruction] = [nop] * target_size
    seen_addresses = set()

    for addr, uinst in instructions:
        if addr < 0:
            raise ValueError(f"Invalid negative address: 0x{addr:03X}")
        if addr in seen_addresses:
            raise ValueError(f"Multiple instructions defined at microcode address 0x{addr:03X}")
        seen_addresses.add(addr)
        result[addr] = uinst

    return result


def emit_binary(instructions: List[MicroInstruction]) -> bytes:
    """Emits machine code bytes (little-endian 32-bit words)."""
    return b"".join(inst.to_bytes() for inst in instructions)


def emit_hex(instructions: List[MicroInstruction]) -> str:
    """Emits Verilog $readmemh ASCII hexadecimal words (one 8-character hex word per line)."""
    return "".join(f"{inst.to_int():08X}\n" for inst in instructions)


def format_micro_instruction(inst: MicroInstruction) -> str:
    """Formats a single MicroInstruction instance into valid Python source code."""
    parts = [f"op=MicroOp.{inst.op.name}"]
    if inst.w == IW.W64:
        parts.append("w=IW.W64")
    if inst.dst != Reg.NONE:
        parts.append(f"dst=Reg.{inst.dst.name}")
    if inst.src1 != Reg.NONE:
        parts.append(f"src1=Reg.{inst.src1.name}")
    if inst.src != Reg.NONE:
        if isinstance(inst.src, FpuTable):
            parts.append(f"src=FpuTable.{inst.src.name}")
        else:
            parts.append(f"src=Reg.{inst.src.name}")
    if inst.op in (MicroOp.JZ, MicroOp.JNZ) or inst.flag.value != 0:
        parts.append(f"flag=StatusFlag.{inst.flag.name}")
    if (
        inst.imm != 0
        or inst.src == Reg.IMM
        or inst.op in (MicroOp.JMP, MicroOp.CALL, MicroOp.JZ, MicroOp.JNZ, MicroOp.LDC)
    ):
        parts.append(f"imm={inst.imm}")
    return f"MicroInstruction({', '.join(parts)})"


def emit_python(
    instructions: List[MicroInstruction],
    symbols: Optional[Dict[str, int]] = None,
) -> str:
    """Generates a complete Python module exporting fpu_ucode and fpu_symbols."""
    lines: List[str] = [
        '"""Auto-generated microcode and symbol table module by fpu_asm."""\n',
        "from typing import Dict, List",
        "from fpu_emu.hardware.reg import Reg",
        "from fpu_emu.hardware.register import StatusFlag",
        "from fpu_emu.micro_instruction import MicroInstruction, IW",
        "from fpu_emu.micro_opcodes import MicroOp",
        "from fpu_emu.rom.fpu_const_map import FpuTable\n\n",
        "fpu_ucode: List[MicroInstruction] = [",
    ]

    user_symbols_by_addr: Dict[int, List[str]] = {}
    if symbols:
        for name, addr in symbols.items():
            if name.upper().startswith("USER_"):
                user_symbols_by_addr.setdefault(addr, []).append(name)

    for idx, inst in enumerate(instructions):
        if idx in user_symbols_by_addr:
            if idx > 0:
                lines.append("")
            for sym_name in sorted(user_symbols_by_addr[idx]):
                lines.append(f"    # {sym_name}")
        lines.append(f"    {format_micro_instruction(inst)},")
    lines.append("]\n")

    lines.append(
        '# Only needs to include the instruction line of the "User_" symbols, sort them when writing to the file.'
    )
    lines.append("fpu_symbols: Dict[str, int] = {")

    if symbols:
        user_symbols = {
            name: addr
            for name, addr in symbols.items()
            if name.upper().startswith("USER_")
        }
        for name, addr in sorted(user_symbols.items(), key=lambda kv: kv[0]):
            lines.append(f'    "{name}": {addr},')

    lines.append("}\n")
    return "\n".join(lines)


def emit_symbols(symbols: Dict[str, int]) -> str:
    """Generates a standard symbol table report separating User_* symbols from other symbols,
    sorted within sections.
    """
    user_symbols = sorted(
        [(k, v) for k, v in symbols.items() if k.upper().startswith("USER_")],
        key=lambda x: x[0],
    )
    other_symbols = sorted(
        [(k, v) for k, v in symbols.items() if not k.upper().startswith("USER_")],
        key=lambda x: x[0],
    )

    max_user_len = max((len(k) for k, _ in user_symbols), default=30) if user_symbols else 30
    max_other_len = max((len(k) for k, _ in other_symbols), default=30) if other_symbols else 30
    col_width = max(max_user_len, max_other_len, 32)

    lines: List[str] = []

    lines.append("[USER_SYMBOLS]")
    lines.append(f"; {'Symbol':<{col_width}} {'Address':<8} Line")
    for name, addr in user_symbols:
        lines.append(f"{name:<{col_width}} 0x{addr:04X}   {addr}")

    lines.append("")
    lines.append("[OTHER_SYMBOLS]")
    lines.append(f"; {'Symbol':<{col_width}} {'Address':<8} Line")
    for name, addr in other_symbols:
        lines.append(f"{name:<{col_width}} 0x{addr:04X}   {addr}")

    lines.append("")
    return "\n".join(lines)


def write_symbol_table(symbols: Dict[str, int], sym_path: Union[str, Path]) -> None:
    """Writes the formatted symbol table report to a file."""
    path = Path(sym_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(emit_symbols(symbols), encoding="utf-8")


def write_output(
    instructions: List[MicroInstruction],
    output_path: Union[str, Path],
    format_type: Optional[str] = "auto",
    symbols: Optional[Dict[str, int]] = None,
) -> None:
    """Writes padded instructions to an output binary, hex, or python file."""
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    fmt = format_type.lower() if format_type else "auto"
    if fmt == "auto":
        ext = path.suffix.lower()
        if ext == ".hex":
            fmt = "hex"
        elif ext == ".py":
            fmt = "py"
        else:
            fmt = "bin"

    if fmt == "hex":
        path.write_text(emit_hex(instructions), encoding="ascii")
    elif fmt == "bin":
        path.write_bytes(emit_binary(instructions))
    elif fmt == "py":
        path.write_text(emit_python(instructions, symbols=symbols), encoding="utf-8")
    else:
        raise ValueError(
            f"Unsupported output format: '{fmt}'. Expected 'bin', 'hex', 'py', or 'auto'."
        )

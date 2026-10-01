"""Register-to-register move (MOV) operations.

Per SystemDesign.md Section 3 (Datapath Architecture) and Section 4.2 / 4.3:
- Single-cycle 32-bit move: HB_BUS -> PASS_B -> RES_BUS -> WE_<dst> (1 clock cycle).
- Two-cycle 64-bit move: Lower half in cycle 1, upper half in cycle 2 (2 clock cycles).
- Supports general registers (AL, AH, BL, BH, DL, DH, FL, FH), compound 64-bit
  registers (AX, BX, DX, FX), exponent registers (EA, EB), and counter (C).
- Status flags are completely unaffected.
"""

from typing import Union
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import HalfSelect, Reg

REG_64 = (Reg.AX, Reg.BX, Reg.DX, Reg.FX)
REG_32 = (
    Reg.AL,
    Reg.AH,
    Reg.BL,
    Reg.BH,
    Reg.DL,
    Reg.DH,
    Reg.FL,
    Reg.FH,
    Reg.EA,
    Reg.EB,
    Reg.C,
)


def mov32(hw: Hardware, dst: Union[Reg, str], src: Union[Reg, str]) -> None:
    """Executes a 32-bit register-to-register move in 1 clock cycle."""
    if isinstance(dst, str):
        dst = Reg[dst.upper()]
    if isinstance(src, str):
        src = Reg[src.upper()]

    if dst in REG_64 or src in REG_64:
        raise ValueError(f"mov32 called with 64-bit register: dst={dst}, src={src}")

    hw.clock.tick(1)
    half = HalfSelect.HI if src in (Reg.AH, Reg.BH, Reg.DH, Reg.FH) else HalfSelect.LO
    hw.reg.set_hb_bus_mux(half, src)
    data = hw.reg.read_hb_bus()
    hw.reg.set_res_bus(dst, data)


def mov64(hw: Hardware, dst: Union[Reg, str], src: Union[Reg, str]) -> None:
    """Executes a 64-bit compound register-to-register move in 2 clock cycles."""
    if isinstance(dst, str):
        dst = Reg[dst.upper()]
    if isinstance(src, str):
        src = Reg[src.upper()]

    if dst not in REG_64 or src not in REG_64:
        raise ValueError(f"mov64 requires 64-bit compound registers: dst={dst}, src={src}")

    dst_lo = Reg[f"{dst.name[0]}L"]
    dst_hi = Reg[f"{dst.name[0]}H"]

    # Cycle 1: Low half
    hw.clock.tick(1)
    hw.reg.set_hb_bus_mux(HalfSelect.LO, src)
    data_lo = hw.reg.read_hb_bus()
    hw.reg.set_res_bus(dst_lo, data_lo)

    # Cycle 2: High half
    hw.clock.tick(1)
    hw.reg.set_hb_bus_mux(HalfSelect.HI, src)
    data_hi = hw.reg.read_hb_bus()
    hw.reg.set_res_bus(dst_hi, data_hi)


def mov(hw: Hardware, dst: Union[Reg, str], src: Union[Reg, str]) -> None:
    """Dispatches a register-to-register move based on operand width."""
    if isinstance(dst, str):
        dst = Reg[dst.upper()]
    if isinstance(src, str):
        src = Reg[src.upper()]

    if dst in REG_64 and src in REG_64:
        mov64(hw, dst, src)
    elif dst in REG_32 and src in REG_32:
        mov32(hw, dst, src)
    else:
        raise ValueError(f"Mismatched register widths for MOV: dst={dst}, src={src}")

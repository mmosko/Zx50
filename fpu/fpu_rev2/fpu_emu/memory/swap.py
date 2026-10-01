"""Register swap operations via microcode transfers.

Per Option B (Microcode approach using FL as temporary scratch register):
- Each 32-bit register exchange uses 3 single-cycle moves through HB_BUS and RES_BUS:
    1. FL <- reg_b (1 clock cycle)
    2. reg_b <- reg_a (1 clock cycle)
    3. reg_a <- FL (1 clock cycle)
  Total: 3 clock cycles for 32-bit registers (or EA/EB).
- When swapping AL and BL (or AX and BX), sign_a and sign_b latches are exchanged.
- 64-bit compound register exchange (swap64) executes 2 consecutive 32-bit swaps
  (lower halves then upper halves), taking 6 clock cycles total.
- Status flags are completely unaffected.
"""

from fpu_emu.hardware import Hardware
from fpu_emu.memory import mov
from fpu_emu.memory.registers import Reg


def swap32(
    hw: Hardware,
    reg_a: Reg,
    reg_b: Reg,
) -> None:
    """Exchanges two 32-bit registers using FL as temporary register (3 clock cycles)."""
    if reg_a.is_64() or reg_b.is_64():
        raise ValueError(f"swap32 cannot be used with 64-bit registers: {reg_a}, {reg_b}")

    if reg_a in (Reg.FL, Reg.FH) or reg_b in (Reg.FL, Reg.FH):
        raise ValueError(f"Cannot swap volatile scratch register FL/FH: {reg_a}, {reg_b}")

    if reg_a in (Reg.SP, Reg.OSP) or reg_b in (Reg.SP, Reg.OSP):
        raise ValueError(f"Unsupported registers for swap32: {reg_a}, {reg_b}")

    if reg_a == reg_b:
        return

    # Microcode transfer sequence via HB_BUS -> PASS_B -> RES_BUS:
    # Option B: FL is the dedicated volatile scratch register.
    # 1. FL <- reg_b
    # 2. reg_b <- reg_a
    # 3. reg_a <- FL
    # This will throw an error if the register src or dst is not feasible
    mov.mov32(hw, Reg.FL, reg_b)
    mov.mov32(hw, reg_b, reg_a)
    mov.mov32(hw, reg_a, Reg.FL)

    # Exchanging AL and BL also exchanges their sign latches
    if (reg_a == Reg.AL and reg_b == Reg.BL) or (reg_a == Reg.BL and reg_b == Reg.AL):
        hw.reg.sign_a, hw.reg.sign_b = hw.reg.sign_b, hw.reg.sign_a


def swap64(
    hw: Hardware,
    reg_a: Reg,
    reg_b: Reg,
) -> None:
    """Exchanges two 64-bit compound registers (6 clock cycles total)."""
    if isinstance(reg_a, str):
        reg_a = Reg[reg_a.upper()]
    if isinstance(reg_b, str):
        reg_b = Reg[reg_b.upper()]

    if not (reg_a.is_64() and reg_b.is_64()):
        raise ValueError(f"swap64 requires 64-bit compound registers: {reg_a}, {reg_b}")

    if reg_a == Reg.FX or reg_b == Reg.FX:
        raise ValueError(f"Cannot swap volatile scratch register FX: {reg_a}, {reg_b}")

    if reg_a == reg_b:
        return

    reg_a_lo = reg_a.lo_half()
    reg_a_hi = reg_a.hi_half()
    reg_b_lo = reg_b.lo_half()
    reg_b_hi = reg_b.hi_half()

    # Swap low halves (3 cycles, exchanges sign_a/sign_b if AX/BX)
    swap32(hw, reg_a_lo, reg_b_lo)

    # Swap high halves (3 cycles)
    swap32(hw, reg_a_hi, reg_b_hi)


def swap_exp(hw: Hardware) -> None:
    """Exchanges 12-bit exponent registers EA and EB using FL as temporary register (3 clock cycles)."""
    # 1. FL <- EB
    # 2. EB <- EA
    # 3. EA <- FL
    mov.mov32(hw, Reg.FL, Reg.EB)
    mov.mov32(hw, Reg.EB, Reg.EA)
    mov.mov32(hw, Reg.EA, Reg.FL)


def swap(
    hw: Hardware,
    reg_a: Reg,
    reg_b: Reg,
) -> None:
    """Dispatches register swap based on register width and type."""
    if isinstance(reg_a, str):
        reg_a = Reg[reg_a.upper()]
    if isinstance(reg_b, str):
        reg_b = Reg[reg_b.upper()]

    if reg_a in (Reg.EA, Reg.EB) and reg_b in (Reg.EA, Reg.EB):
        swap_exp(hw)
    elif reg_a.is_64() and reg_b.is_64():
        swap64(hw, reg_a, reg_b)
    elif reg_a.is_32() and reg_b.is_32():
        swap32(hw, reg_a, reg_b)
    else:
        raise ValueError(f"Mismatched or unsupported registers for SWAP: {reg_a}, {reg_b}")

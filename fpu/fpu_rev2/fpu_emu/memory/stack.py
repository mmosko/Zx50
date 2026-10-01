"""Hardware stack operations on SysMEM EBR (0x0000 - 0x00FF).

Per SystemDesign.md Section 5.1 & Section 4.3:
- Stack grows upward from 0x0000 to 0x00FF (256 bytes, 64 32-bit words).
- SP points to the next free byte on the stack.
- Stack boundary violations set UNDERFLOW/OVERFLOW and ERR in Status register.
- Memory access takes 1 clock cycle for 32-bit, 2 clock cycles for 64-bit.
"""

from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag

STACK_BASE = 0x0000
STACK_LIMIT = 256  # 256 bytes total stack space


def push32(hw: Hardware, src: Reg):
    """Pushes a 32-bit register onto the stack (1 memory cycle)."""
    hw.clock.tick(1)
    sp = hw.reg.sp
    if sp + 4 > STACK_LIMIT:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    data = bytearray(getattr(hw.reg, f"_{src.name.lower()}"))
    hw.mem.store(STACK_BASE + sp, data)
    hw.reg.sp = sp + 4


def pop32(hw: Hardware, dst: Reg):
    """Pops a 32-bit value from the stack into dst register (1 memory cycle)."""
    hw.clock.tick(1)
    sp = hw.reg.sp
    if sp < 4:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    new_sp = sp - 4
    data = hw.mem.load(STACK_BASE + new_sp, 4)
    hw.reg.set_res_bus(dst, data)
    hw.reg.sp = new_sp


def push64(hw: Hardware, src: Reg):
    """Pushes a 64-bit register onto the stack (2 memory cycles)."""
    hw.clock.tick(2)
    sp = hw.reg.sp
    if sp + 8 > STACK_LIMIT:
        hw.reg.set_flag(StatusFlag.OVERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    lo = getattr(hw.reg, f"_{src.name[0].lower()}l")
    hi = getattr(hw.reg, f"_{src.name[0].lower()}h")
    data = bytearray(lo) + bytearray(hi)
    hw.mem.store(STACK_BASE + sp, data)
    hw.reg.sp = sp + 8


def pop64(hw: Hardware, dst: Reg):
    """Pops a 64-bit value from the stack into dst register (2 memory cycles)."""
    hw.clock.tick(1)
    sp = hw.reg.sp
    if sp < 8:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return

    new_sp = sp - 8
    data = hw.mem.load(STACK_BASE + new_sp, 8)
    dst_lo = Reg[dst.name[0] + "L"]
    dst_hi = Reg[dst.name[0] + "H"]
    hw.reg.set_res_bus(dst_lo, data[0:4])
    hw.clock.tick(1)
    hw.reg.set_res_bus(dst_hi, data[4:8])
    hw.reg.sp = new_sp


def peek32(hw: Hardware) -> bytearray:
    """Peeks at the 32-bit value currently on top of the stack without popping (1 memory cycle)."""
    hw.clock.tick(1)
    sp = hw.reg.sp
    if sp < 4:
        hw.reg.set_flag(StatusFlag.UNDERFLOW, True)
        hw.reg.set_flag(StatusFlag.ERR, True)
        return bytearray(4)
    return hw.mem.load(STACK_BASE + (sp - 4), 4)

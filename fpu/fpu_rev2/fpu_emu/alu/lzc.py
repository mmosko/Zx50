"""32-bit and 64-bit Leading-Zero Counter primitive (alu_lzc).

Per SystemDesign.md Section 3.3, Section 3.8, and Section 4:
- Evaluates AL (32-bit mantissa) or AX (64-bit compound mantissa).
- Single-cycle priority encoding tree (1 cycle execution).
- Destination: Loads result directly into loop/shift counter C.
  * For 32-bit: C[5:0] <- LZC(AL), range 0..32.
  * For 64-bit: C[5:0] <- LZC(AX), range 0..64.
- Flag updates:
  * ZF: Set to 1 if input operand is zero, cleared to 0 otherwise.
  * SF: Cleared to 0.
  * Other flags (CF, VF, UF, ERR) remain unaffected.
"""

from typing import Tuple
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg, StatusFlag, Registers

# Width constants
WIDTH_32_BYTES = 4
WIDTH_64_BYTES = 8
BITS_PER_BYTE = 8


def lzc_core(val_bytes: bytearray, width_bytes: int = WIDTH_32_BYTES) -> Tuple[int, bool]:
    """Pure functional priority encoding datapath for leading-zero counting.

    :param val_bytes: Input data as Little-Endian bytearray (4 or 8 bytes).
    :param width_bytes: 4 (32-bit) or 8 (64-bit).
    :return: (count, zf) where count is range 0..32 (or 0..64) and zf is True if val == 0.
    """
    if width_bytes not in (WIDTH_32_BYTES, WIDTH_64_BYTES):
        raise ValueError(f"Unsupported LZC width: {width_bytes} bytes")

    total_bits = width_bytes * BITS_PER_BYTE
    val = Registers.to_int(val_bytes)

    if val == 0:
        return total_bits, True

    leading_zeros = total_bits - val.bit_length()
    return leading_zeros, False


def lzc32(hw: Hardware, reg: Reg = Reg.AL) -> int:
    """Executes single-cycle LZC on 32-bit register (default AL), loading result into C."""
    hw.clock.tick(1)
    val_bytes = hw.reg.get(reg)
    count, zf = lzc_core(val_bytes, width_bytes=WIDTH_32_BYTES)

    hw.reg.c = count
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, False)
    return count


def lzc64(hw: Hardware, reg: Reg = Reg.AX) -> int:
    """Executes single-cycle LZC on 64-bit register (default AX), loading result into C."""
    hw.clock.tick(1)
    val_bytes = hw.reg.get(reg)
    count, zf = lzc_core(val_bytes, width_bytes=WIDTH_64_BYTES)

    hw.reg.c = count
    hw.reg.set_flag(StatusFlag.ZERO, zf)
    hw.reg.set_flag(StatusFlag.SIGN, False)
    return count

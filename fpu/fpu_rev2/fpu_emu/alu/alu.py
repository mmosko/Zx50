"""Arithmetic Logic Unit top-level coordinator for Zx50 FPU."""

from typing import Optional
from fpu_emu.hardware import Hardware
from fpu_emu.memory.registers import Reg
from fpu_emu.alu import adder
from fpu_emu.alu import shifter
from fpu_emu.alu import lzc
from fpu_emu.alu import logic
from fpu_emu.alu import booth_mul
from fpu_emu.alu import ieee754_exp
from fpu_emu.alu import fp_sqrt
from fpu_emu.alu import fp_mul_div
from fpu_emu.alu import fp_ln
from fpu_emu.alu import fp_exp
from fpu_emu.alu import fp_pow


class Alu:
    """ALU coordinator interfacing execution primitives with physical Hardware."""

    def __init__(self, hw: Hardware):
        self._hw = hw

    @property
    def hw(self) -> Hardware:
        return self._hw

    # -------------------------------------------------------------------------
    # Adder / Subtractor API (ADD, ADC, SUB, SBB, CMP)
    # -------------------------------------------------------------------------
    def add32(self, src: Reg):
        adder.add32(self._hw, src)

    def adc32(self, src: Reg):
        adder.adc32(self._hw, src)

    def sub32(self, src: Reg):
        adder.sub32(self._hw, src)

    def sbb32(self, src: Reg):
        adder.sbb32(self._hw, src)

    def cmp32(self, src: Reg):
        adder.cmp32(self._hw, src)

    def add64(self, src: Reg):
        adder.add64(self._hw, src)

    def adc64(self, src: Reg):
        adder.adc64(self._hw, src)

    def sub64(self, src: Reg):
        adder.sub64(self._hw, src)

    def sbb64(self, src: Reg):
        adder.sbb64(self._hw, src)

    def cmp64(self, src: Reg):
        adder.cmp64(self._hw, src)

    # -------------------------------------------------------------------------
    # Barrel Shifter API (LSL, LSR, ASR)
    # -------------------------------------------------------------------------
    def lsl32(self, shift: Optional[int] = None, reg: Reg = Reg.AL):
        shifter.lsl32(self._hw, shift, reg)

    def lsr32(self, shift: Optional[int] = None, reg: Reg = Reg.AL):
        shifter.lsr32(self._hw, shift, reg)

    def asr32(self, shift: Optional[int] = None, reg: Reg = Reg.AL):
        shifter.asr32(self._hw, shift, reg)

    def lsl64(self, shift: Optional[int] = None, reg: Reg = Reg.AX):
        shifter.lsl64(self._hw, shift, reg)

    def lsr64(self, shift: Optional[int] = None, reg: Reg = Reg.AX):
        shifter.lsr64(self._hw, shift, reg)

    def asr64(self, shift: Optional[int] = None, reg: Reg = Reg.AX):
        shifter.asr64(self._hw, shift, reg)

    def rrc32(self, reg: Reg = Reg.AL):
        shifter.rrc32(self._hw, reg)

    def rrc64(self, reg: Reg = Reg.AX):
        shifter.rrc64(self._hw, reg)

    # -------------------------------------------------------------------------
    # Leading Zero Counter API (LZC)
    # -------------------------------------------------------------------------
    def lzc32(self, reg: Reg = Reg.AL) -> int:
        return lzc.lzc32(self._hw, reg)

    def lzc64(self, reg: Reg = Reg.AX) -> int:
        return lzc.lzc64(self._hw, reg)

    # -------------------------------------------------------------------------
    # Bitwise Logic & Sign Manipulator API (AND, OR, XOR, NOT, CHS, ABS)
    # -------------------------------------------------------------------------
    def and32(self, src: Reg, dst: Reg = Reg.AL):
        logic.and32(self._hw, src, dst)

    def or32(self, src: Reg, dst: Reg = Reg.AL):
        logic.or32(self._hw, src, dst)

    def xor32(self, src: Reg, dst: Reg = Reg.AL):
        logic.xor32(self._hw, src, dst)

    def not32(self, dst: Reg = Reg.AL):
        logic.not32(self._hw, dst)

    def and64(self, src: Reg, dst: Reg = Reg.AX):
        logic.and64(self._hw, src, dst)

    def or64(self, src: Reg, dst: Reg = Reg.AX):
        logic.or64(self._hw, src, dst)

    def xor64(self, src: Reg, dst: Reg = Reg.AX):
        logic.xor64(self._hw, src, dst)

    def not64(self, dst: Reg = Reg.AX):
        logic.not64(self._hw, dst)

    def chs(self, reg: Reg = Reg.AH):
        logic.chs(self._hw, reg)

    def abs_val(self, reg: Reg = Reg.AH):
        logic.abs_val(self._hw, reg)

    def abs_int32(self, reg: Reg = Reg.AL):
        logic.abs_int32(self._hw, reg)

    def abs_int64(self, reg: Reg = Reg.AX):
        logic.abs_int64(self._hw, reg)

    # -------------------------------------------------------------------------
    # Radix-4 Booth Multiplier API (MUL AL, src / MUL AX, src)
    # -------------------------------------------------------------------------
    def mul32(self, src: Reg = Reg.BL):
        booth_mul.mul32(self._hw, src)

    def mul64(self, src: Reg = Reg.BX):
        booth_mul.mul64(self._hw, src)

    def mul_f32(self, dst: Reg = Reg.AL, src: Reg = Reg.BL):
        fp_mul_div.mul_f32(self._hw, dst, src)

    def div_f32(self, dst: Reg = Reg.AL, src: Reg = Reg.BL):
        fp_mul_div.div_f32(self._hw, dst, src)

    def mul_f64(self, dst: Reg = Reg.AX, src: Reg = Reg.BX):
        fp_mul_div.mul_f64(self._hw, dst, src)

    def div_f64(self, dst: Reg = Reg.AX, src: Reg = Reg.BX):
        fp_mul_div.div_f64(self._hw, dst, src)

    # -------------------------------------------------------------------------
    # 12-Bit Exponent ALU API (alu_exp12 / ieee754_exp)
    # -------------------------------------------------------------------------
    def exp_add(self):
        ieee754_exp.exp_add(self._hw)

    def exp_sub(self):
        ieee754_exp.exp_sub(self._hw)

    def exp_diff(self, reg: Reg = Reg.AL):
        ieee754_exp.exp_diff(self._hw, reg=reg)

    def exp_add_mul(self, bias: int = ieee754_exp.BIAS_F32):
        ieee754_exp.exp_add_mul(self._hw, bias=bias)

    def exp_sub_div(self, bias: int = ieee754_exp.BIAS_F32):
        ieee754_exp.exp_sub_div(self._hw, bias=bias)

    def exp_adj_norm(self, shift_count: Optional[int] = None):
        ieee754_exp.exp_adj_norm(self._hw, shift_count=shift_count)

    def exp_inc(self):
        ieee754_exp.exp_inc(self._hw)

    def exp_dec(self):
        ieee754_exp.exp_dec(self._hw)

    def unpack_f32(
        self,
        src: Reg = Reg.AL,
        dst_mantissa: Reg = Reg.AL,
        dst_exp: Reg = Reg.EA,
    ) -> int:
        return ieee754_exp.unpack_f32(self._hw, src=src, dst_mantissa=dst_mantissa, dst_exp=dst_exp)

    def pack_f32(
        self,
        sign: Optional[int] = None,
        src_mantissa: Reg = Reg.AL,
        src_exp: Reg = Reg.EA,
        dst: Reg = Reg.AL,
    ):
        ieee754_exp.pack_f32(self._hw, sign=sign, src_mantissa=src_mantissa, src_exp=src_exp, dst=dst)

    def unpack_f64(
        self,
        src: Reg = Reg.AX,
        dst_mantissa: Reg = Reg.AX,
        dst_exp: Reg = Reg.EA,
    ) -> int:
        return ieee754_exp.unpack_f64(self._hw, src=src, dst_mantissa=dst_mantissa, dst_exp=dst_exp)

    def pack_f64(
        self,
        sign: Optional[int] = None,
        src_mantissa: Reg = Reg.AX,
        src_exp: Reg = Reg.EA,
        dst: Reg = Reg.AX,
    ):
        ieee754_exp.pack_f64(self._hw, sign=sign, src_mantissa=src_mantissa, src_exp=src_exp, dst=dst)

    def swap(self, reg_a: Reg, reg_b: Reg):
        ieee754_exp.swap(self._hw, reg_a=reg_a, reg_b=reg_b)

    # -------------------------------------------------------------------------
    # Floating-Point Square Root API
    # -------------------------------------------------------------------------
    def sqrt_exp32(self, exp_reg: Reg = Reg.EA) -> bool:
        from fpu_emu.memory.registers import Registers
        ea = self._hw.reg.ea if exp_reg == Reg.EA else self._hw.reg.eb
        new_ea, is_odd = fp_sqrt.sqrt_exp_f32(ea)
        if exp_reg == Reg.EA:
            self._hw.reg.ea = new_ea
        else:
            self._hw.reg.eb = new_ea
        return is_odd

    def sqrt_exp64(self, exp_reg: Reg = Reg.EA) -> bool:
        from fpu_emu.memory.registers import Registers
        ea = self._hw.reg.ea if exp_reg == Reg.EA else self._hw.reg.eb
        new_ea, is_odd = fp_sqrt.sqrt_exp_f64(ea)
        if exp_reg == Reg.EA:
            self._hw.reg.ea = new_ea
        else:
            self._hw.reg.eb = new_ea
        return is_odd

    def sqrt_core32(self, is_odd: bool, dst: Reg = Reg.AL):
        from fpu_emu.memory.registers import Registers
        res = fp_sqrt.sqrt_mantissa_core_f32(self._hw, is_odd=is_odd)
        self._hw.reg.set(dst, Registers.from_int(res, 4))

    def sqrt_core64(self, is_odd: bool, dst: Reg = Reg.AX):
        from fpu_emu.memory.registers import Registers
        res = fp_sqrt.sqrt_mantissa_core_f64(self._hw, is_odd=is_odd)
        self._hw.reg.set(dst, Registers.from_int(res, 8))

    # -------------------------------------------------------------------------
    # Floating-Point Natural Log, Exponential, and Power API
    # -------------------------------------------------------------------------
    def ln_f32(self):
        fp_ln.ln_f32(self._hw)

    def ln_f64(self):
        fp_ln.ln_f64(self._hw)

    def exp_f32(self):
        fp_exp.exp_f32(self._hw)

    def exp_f64(self):
        fp_exp.exp_f64(self._hw)

    def pow_f32(self, dst: Reg = Reg.AL, src: Reg = Reg.BL):
        fp_pow.pow_f32(self._hw, dst=dst, src=src)

    def pow_f64(self, dst: Reg = Reg.AX, src: Reg = Reg.BX):
        fp_pow.pow_f64(self._hw, dst=dst, src=src)

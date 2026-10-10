from typing import Callable, Union

from fpu_emu.blocks.adder.adder_core import AdderCore, AdderResult
from fpu_emu.blocks.adder.booth_mul import BoothMulCore, BoothMulResult
from fpu_emu.blocks.adder.div_core import DivCore, DivResult
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


@fpga_resource(
    approach="Adder controller, 32/64-bit sequencer, exponent bounds comparators, and IEEE-754 pack/unpack logic",
    luts=75,
    ffs=14,
    delay_ns=2.6,
    cycles=1,
    shared_unit="adder_block",
)
class AdderBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock):
        super().__init__(name, inputs, memory, writeback, clock)
        assert isinstance(inputs.ha_mux, Mux)
        self._ha_mux: Mux = inputs.ha_mux

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.ADD:
                self._add(instr)
            case MicroOp.ADC:
                self._adc(instr)
            case MicroOp.SUB:
                self._sub(instr)
            case MicroOp.SBB:
                self._sbb(instr)
            case MicroOp.CMP:
                self._cmp32(instr)
            case MicroOp.EXP_ADD:
                self._exp_add(instr)
            case MicroOp.EXP_SUB:
                self._exp_sub(instr)
            case MicroOp.PACK:
                self._pack(instr)
            case MicroOp.UNPACK:
                self._unpack(instr)
            case MicroOp.MUL:
                self._mul(instr, signed=True)
            case MicroOp.MULU:
                self._mul(instr, signed=False)
            case MicroOp.DIV:
                self._div(instr, signed=True)
            case MicroOp.DIVU:
                self._div(instr, signed=False)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _add(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.ADD)
        if instr.is_w32():
            self._add_32(instr, cin=0, sub=False)
        else:
            self._add_64(instr, cin=0, sub=False)

    def _adc(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.ADC)
        cin = 1 if self._inputs.status.is_bit_set(StatusFlag.CARRY) else 0
        if instr.is_w32():
            self._add_32(instr, cin=cin, sub=False)
        else:
            self._add_64(instr, cin=cin, sub=False)

    def _sub(self, instr: MicroInstruction):
        if instr.is_w32():
            self._add_32(instr, cin=0, sub=True)
        else:
            self._add_64(instr, cin=0, sub=True)

    def _sbb(self, instr: MicroInstruction):
        borrow_in = 1 if self._inputs.status.is_bit_set(StatusFlag.CARRY) else 0
        if instr.is_w32():
            self._add_32(instr, cin=borrow_in, sub=True)
        else:
            self._add_64(instr, cin=borrow_in, sub=True)

    def _combinatorial_add(self, cin: int, sub: bool) -> AdderResult:
        ha_bus = self._inputs.ha_mux.read()
        hb_bus = self._inputs.hb_mux.read()
        return AdderCore.adder_core(a=ha_bus, b=hb_bus, cin=cin, sub=sub)

    def _add_32(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """
        32-bit Add with carry

            instr.dst <- instr.dst - instr.src

        This allows 32-bit math on EA, EB, and C, in addition to AL or AH

        :param instr:
        :param cin:
        :param sub:
        :return:
        """
        assert (instr.src is not Reg.NONE)
        assert (instr.dst is not Reg.NONE)

        # Combinatorial setup in current cycle
        src1 = instr.src1 if instr.src1 is not Reg.NONE else instr.dst
        self._ha_mux.select(src1.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=cin, sub=sub)

        # Writeback AL (edge-triggered tick in writeback)
        self._outputs.block_res.set(adder_result.res)
        self._outputs.block_res_sel.set(instr.dst.value)
        self._outputs.exec_done.set(1)
        self._wb_flags(adder_result)
        self._writeback()

    def _add_64(self, instr: MicroInstruction, cin: int, sub: bool) -> None:
        """ADD dst, src: 64-bit addition with carry (2 cycles)."""
        assert (instr.src is not Reg.NONE)
        self._validate_src64(instr.src)

        dst = instr.dst if instr.dst is not Reg.NONE else Reg.AL
        src1 = instr.src1 if instr.src1 is not Reg.NONE else dst
        self._validate_src64(src1)
        self._validate_src64(dst)

        # Low word
        self._ha_mux.select(src1.value)
        self._inputs.hb_mux.select(instr.src.value)
        low_result = self._combinatorial_add(cin=cin, sub=sub)

        # Writeback low word (status write disabled for intermediate low word)
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(low_result.res)
        self._outputs.block_res_sel.set(dst.value)
        self._writeback()

        # Upper word with carry from lower word
        cin_high = 1 if low_result.cf else 0
        self._ha_mux.select(src1.value | 0b0001)
        src_h = instr.src.value | 0b0001
        self._inputs.hb_mux.select(src_h)
        high_result = self._combinatorial_add(cin=cin_high, sub=sub)

        # Writeback high word and commit final status flags (ZF is 1 only if both halves are zero)
        final_result = AdderResult(
            res=high_result.res,
            cf=high_result.cf,
            zf=low_result.zf and high_result.zf,
            sf=high_result.sf,
            vf=high_result.vf,
        )
        self._wb_flags(final_result)
        self._outputs.block_res.set(high_result.res)
        self._outputs.block_res_sel.set(dst.value | 0b0001)
        self._outputs.exec_done.set(1)
        self._writeback()

    @staticmethod
    def _validate_src64(src: Reg):
        # must be the low word of a 64-bit pair
        assert src.is_lo_half()

    def _cmp32(self, instr: MicroInstruction):
        """CMP dst, src: 32-bit compare dst - src without modifying dst (1 cycle)."""
        assert (instr.src is not None)
        assert (instr.dst is not None)
        src1 = instr.src1 if instr.src1 is not Reg.NONE else instr.dst
        self._ha_mux.select(src1.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=0, sub=True)

        self._outputs.block_res_sel.set(Reg.NONE.value)  # No register writeback
        self._wb_flags(adder_result)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _wb_flags(self, result: Union[AdderResult, BoothMulResult, DivResult]):
        status_byte = 0
        status_byte |= result.cf << StatusFlag.CARRY.value
        status_byte |= result.sf << StatusFlag.SIGN.value
        status_byte |= result.vf << StatusFlag.OVERFLOW.value
        status_byte |= result.zf << StatusFlag.ZERO.value
        err = getattr(result, "err", False)
        status_byte |= err << StatusFlag.ERR.value
        self._outputs.res_status.set(status_byte)

        status_wr_select = (1 << StatusFlag.CARRY.value) | \
                           (1 << StatusFlag.SIGN.value) | \
                           (1 << StatusFlag.OVERFLOW.value) | \
                           (1 << StatusFlag.ZERO.value)
        if hasattr(result, "err"):
            status_wr_select |= (1 << StatusFlag.ERR.value)

        self._outputs.status_wr_sel.set(status_wr_select)

    LIMIT_EXP_MAX = 1023
    LIMIT_EXP_MIN = -1022
    MASK_12BIT = 0x0FFF
    SIGN_12BIT = 0x0800
    MOD_12BIT = 0x1000

    STATUS_EXP_MASK = (
        (1 << StatusFlag.ZERO.value)
        | (1 << StatusFlag.SIGN.value)
        | (1 << StatusFlag.OVERFLOW.value)
        | (1 << StatusFlag.UNDERFLOW.value)
    )

    def _exp_add(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.EXP_ADD
        self._exp_op(instr, sub=False)

    def _exp_sub(self, instr: MicroInstruction) -> None:
        assert instr.op == MicroOp.EXP_SUB
        self._exp_op(instr, sub=True)

    def _exp_op(self, instr: MicroInstruction, sub: bool) -> None:
        assert instr.src is not Reg.NONE
        dst = instr.dst if instr.dst is not Reg.NONE else Reg.EA
        src1 = instr.src1 if instr.src1 is not Reg.NONE else dst

        self._ha_mux.select(src1.value)
        self._inputs.hb_mux.select(instr.src.value)
        adder_result = self._combinatorial_add(cin=0, sub=sub)

        # Result is computed entirely by adder_core on sign-extended inputs
        res_s = int.from_bytes(adder_result.res, byteorder="little", signed=True)
        res_12 = res_s & self.MASK_12BIT

        ovf = res_s > self.LIMIT_EXP_MAX
        uf = res_s < self.LIMIT_EXP_MIN
        zf = res_12 == 0
        sf = bool(res_12 & self.SIGN_12BIT)

        self._outputs.block_res.set(res_12)
        self._outputs.block_res_sel.set(dst.value)

        status_byte = (
            (int(zf) << StatusFlag.ZERO.value)
            | (int(sf) << StatusFlag.SIGN.value)
            | (int(ovf) << StatusFlag.OVERFLOW.value)
            | (int(uf) << StatusFlag.UNDERFLOW.value)
        )
        self._outputs.res_status.set(status_byte)
        self._outputs.status_wr_sel.set(self.STATUS_EXP_MASK)
        self._outputs.exec_done.set(1)
        self._writeback()

    LIMIT_F32_EXP_MAX = 255
    LIMIT_F32_EXP_MIN = 0
    LIMIT_F64_EXP_MAX = 2047
    LIMIT_F64_EXP_MIN = 0

    STATUS_PACK_MASK = (
        (1 << StatusFlag.ZERO.value)
        | (1 << StatusFlag.SIGN.value)
        | (1 << StatusFlag.OVERFLOW.value)
        | (1 << StatusFlag.UNDERFLOW.value)
    )

    STATUS_UNPACK_MASK = (
        (1 << StatusFlag.ZERO.value)
        | (1 << StatusFlag.SIGN.value)
        | (1 << StatusFlag.DIFF_SIGN.value)
    )

    @staticmethod
    def _resolve_unpack_pack_regs(instr: MicroInstruction) -> tuple[Reg, Reg]:
        """Resolves (mantissa_reg, exp_reg) from instruction dst and src."""
        assert instr.dst is not Reg.NONE, "Destination register cannot be NONE"
        assert instr.src is not Reg.NONE, "Source register cannot be NONE"
        if instr.dst in (Reg.EA, Reg.EB):
            return instr.src, instr.dst
        return instr.dst, instr.src

    def _unpack(self, instr: MicroInstruction) -> None:
        if instr.is_w32():
            self._unpack_32(instr)
        else:
            self._unpack_64(instr)

    def _unpack_32(self, instr: MicroInstruction) -> None:
        mantissa_reg, exp_reg = self._resolve_unpack_pack_regs(instr)

        # Read float value from mantissa_reg via HB_MUX
        self._inputs.hb_mux.select(mantissa_reg.value)
        raw_val = self._inputs.hb_mux.read_int()

        sign_bit = (raw_val >> 31) & 1
        exp_val = (raw_val >> 23) & 0xFF
        frac = raw_val & 0x007FFFFF
        is_zero = (raw_val & 0x7FFFFFFF) == 0

        # Hidden bit at bit 23 restored for normalized float (exp != 0)
        mantissa = ((1 << 23) | frac) if exp_val != 0 else frac

        prev_s = 1 if self._inputs.status.is_bit_set(StatusFlag.SIGN) else 0
        diff_sign = prev_s ^ sign_bit
        status_byte = (
            (int(is_zero) << StatusFlag.ZERO.value)
            | (sign_bit << StatusFlag.SIGN.value)
            | (diff_sign << StatusFlag.DIFF_SIGN.value)
        )

        # Cycle 1: Write exponent into exp_reg (EA or EB)
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(exp_val)
        self._outputs.block_res_sel.set(exp_reg.value)
        self._writeback()

        # Cycle 2: Write restored mantissa into mantissa_reg and commit status flags
        self._outputs.res_status.set(status_byte)
        self._outputs.status_wr_sel.set(self.STATUS_UNPACK_MASK)
        self._outputs.block_res.set(mantissa)
        self._outputs.block_res_sel.set(mantissa_reg.value)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _unpack_64(self, instr: MicroInstruction) -> None:
        mantissa_reg, exp_reg = self._resolve_unpack_pack_regs(instr)
        self._validate_src64(mantissa_reg)
        mantissa_reg_hi = Reg(mantissa_reg.value | 0b0001)

        # Read high and low words via HB_MUX
        self._inputs.hb_mux.select(mantissa_reg_hi.value)
        raw_hi = self._inputs.hb_mux.read_int()
        self._inputs.hb_mux.select(mantissa_reg.value)
        raw_lo = self._inputs.hb_mux.read_int()

        sign_bit = (raw_hi >> 31) & 1
        exp_val = (raw_hi >> 20) & 0x7FF
        frac_hi = raw_hi & 0x000FFFFF
        is_zero = ((raw_hi & 0x7FFFFFFF) == 0) and (raw_lo == 0)

        # Hidden bit at bit 20 restored for normalized float (exp != 0)
        mantissa_hi = ((1 << 20) | frac_hi) if exp_val != 0 else frac_hi

        prev_s = 1 if self._inputs.status.is_bit_set(StatusFlag.SIGN) else 0
        diff_sign = prev_s ^ sign_bit
        status_byte = (
            (int(is_zero) << StatusFlag.ZERO.value)
            | (sign_bit << StatusFlag.SIGN.value)
            | (diff_sign << StatusFlag.DIFF_SIGN.value)
        )

        # Cycle 1: Write exponent into exp_reg (EA or EB)
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(exp_val)
        self._outputs.block_res_sel.set(exp_reg.value)
        self._writeback()

        # Cycle 2: Write restored high mantissa into mantissa_reg_hi and commit status flags
        self._outputs.res_status.set(status_byte)
        self._outputs.status_wr_sel.set(self.STATUS_UNPACK_MASK)
        self._outputs.block_res.set(mantissa_hi)
        self._outputs.block_res_sel.set(mantissa_reg_hi.value)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _pack(self, instr: MicroInstruction) -> None:
        if instr.is_w32():
            self._pack_32(instr)
        else:
            self._pack_64(instr)

    def _pack_32(self, instr: MicroInstruction) -> None:
        mantissa_reg, exp_reg = self._resolve_unpack_pack_regs(instr)

        # Read exponent from exp_reg via HA_MUX
        self._ha_mux.select(exp_reg.value)
        exp_s = self._ha_mux.read_int()
        exp_12 = exp_s & self.MASK_12BIT
        if exp_12 & self.SIGN_12BIT:
            exp_s = exp_12 - self.MOD_12BIT
        else:
            exp_s = exp_12

        # Read mantissa from mantissa_reg via HB_MUX
        self._inputs.hb_mux.select(mantissa_reg.value)
        mantissa = self._inputs.hb_mux.read_int()

        sign = 1 if self._inputs.status.is_bit_set(StatusFlag.SIGN) else 0

        is_zero_mantissa = (mantissa == 0)
        vf = False
        uf = False
        zf = False

        if is_zero_mantissa:
            packed = sign << 31
            zf = True
        elif exp_s >= self.LIMIT_F32_EXP_MAX:
            # Exponent overflow to +/-infinity
            vf = True
            packed = (sign << 31) | (0xFF << 23)
        elif exp_s <= self.LIMIT_F32_EXP_MIN:
            # Exponent underflow to signed zero
            uf = True
            zf = True
            packed = sign << 31
        else:
            # Normal float: strip implicit hidden bit 23 and pack
            frac = mantissa & 0x007FFFFF
            packed = (sign << 31) | ((exp_s & 0xFF) << 23) | frac

        status_byte = (
            (int(zf) << StatusFlag.ZERO.value)
            | (sign << StatusFlag.SIGN.value)
            | (int(vf) << StatusFlag.OVERFLOW.value)
            | (int(uf) << StatusFlag.UNDERFLOW.value)
        )

        self._outputs.res_status.set(status_byte)
        self._outputs.status_wr_sel.set(self.STATUS_PACK_MASK)
        self._outputs.block_res.set(packed)
        self._outputs.block_res_sel.set(mantissa_reg.value)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _pack_64(self, instr: MicroInstruction) -> None:
        mantissa_reg, exp_reg = self._resolve_unpack_pack_regs(instr)
        self._validate_src64(mantissa_reg)
        mantissa_reg_hi = Reg(mantissa_reg.value | 0b0001)

        # Read exponent from exp_reg via HA_MUX
        self._ha_mux.select(exp_reg.value)
        exp_s = self._ha_mux.read_int()
        exp_12 = exp_s & self.MASK_12BIT
        if exp_12 & self.SIGN_12BIT:
            exp_s = exp_12 - self.MOD_12BIT
        else:
            exp_s = exp_12

        # Read mantissa low and high words via HB_MUX
        self._inputs.hb_mux.select(mantissa_reg.value)
        mantissa_lo = self._inputs.hb_mux.read_int()
        self._inputs.hb_mux.select(mantissa_reg_hi.value)
        mantissa_hi = self._inputs.hb_mux.read_int()

        sign = 1 if self._inputs.status.is_bit_set(StatusFlag.SIGN) else 0

        is_zero_mantissa = (mantissa_hi == 0 and mantissa_lo == 0)
        vf = False
        uf = False
        zf = False

        if is_zero_mantissa:
            packed_hi = sign << 31
            packed_lo = 0
            zf = True
        elif exp_s >= self.LIMIT_F64_EXP_MAX:
            # Exponent overflow to +/-infinity
            vf = True
            packed_hi = (sign << 31) | (0x7FF << 20)
            packed_lo = 0
        elif exp_s <= self.LIMIT_F64_EXP_MIN:
            # Exponent underflow to signed zero
            uf = True
            zf = True
            packed_hi = sign << 31
            packed_lo = 0
        else:
            # Normal float64: strip implicit hidden bit 20 and pack
            frac_hi = mantissa_hi & 0x000FFFFF
            packed_hi = (sign << 31) | ((exp_s & 0x7FF) << 20) | frac_hi
            packed_lo = mantissa_lo & 0xFFFFFFFF

        status_byte = (
            (int(zf) << StatusFlag.ZERO.value)
            | (sign << StatusFlag.SIGN.value)
            | (int(vf) << StatusFlag.OVERFLOW.value)
            | (int(uf) << StatusFlag.UNDERFLOW.value)
        )

        # Cycle 1: write low word to mantissa_reg
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(packed_lo)
        self._outputs.block_res_sel.set(mantissa_reg.value)
        self._writeback()

        # Cycle 2: write high word to mantissa_reg_hi and commit status flags
        self._outputs.res_status.set(status_byte)
        self._outputs.status_wr_sel.set(self.STATUS_PACK_MASK)
        self._outputs.block_res.set(packed_hi)
        self._outputs.block_res_sel.set(mantissa_reg_hi.value)
        self._outputs.exec_done.set(1)
        self._writeback()


    def _mul(self, instr: MicroInstruction, signed: bool = True) -> None:
        """MUL dst, src: 32-bit multiply yielding 64-bit product in {dst_hi, dst} (16 cycles).

        :param instr: MicroInstruction with dst (e.g. AL) and src (e.g. BL)
        :param signed: True for signed two's-complement multiplication, False for unsigned
        """
        assert instr.src is not Reg.NONE
        if not instr.is_w32():
            raise NotImplementedError("64-bit multiplication is orchestrated via microcode")

        if instr.dst not in (Reg.NONE, Reg.AL):
            raise HardwareBusError(f"MUL destination on HA_MUX must be AL, got {instr.dst}")

        dst = Reg.AL
        dst_hi = Reg.AH

        # Step 1: Combinatorial latch of inputs from HA_MUX and HB_MUX
        self._ha_mux.select(dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        ha_val = self._inputs.ha_mux.read()
        hb_val = self._inputs.hb_mux.read()

        mul_result = BoothMulCore.booth_mul_core(a=ha_val, b=hb_val, signed=signed)

        # Step 2: 14 compute cycles (Radix-4 Booth iteration)
        self._clock.tick(14)

        # Step 3: Cycle 15 - Writeback low word (e.g. AL) without status write
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(mul_result.res[0:4])
        self._outputs.block_res_sel.set(dst.value)
        self._writeback()

        # Step 4: Cycle 16 - Writeback high word (e.g. AH) and commit status flags
        self._outputs.block_res.set(mul_result.res[4:8])
        self._outputs.block_res_sel.set(dst_hi.value)
        self._outputs.exec_done.set(1)
        self._wb_flags(mul_result)
        self._writeback()

    def _div(self, instr: MicroInstruction, signed: bool = True) -> None:
        """DIV dst, src: 32-bit division yielding quotient in AL and remainder in DL (32 cycles).

        :param instr: MicroInstruction with dst (e.g. AL) and src (e.g. BL)
        :param signed: True for signed two's-complement division, False for unsigned
        """
        assert instr.src is not Reg.NONE
        if not instr.is_w32():
            raise NotImplementedError("64-bit division is orchestrated via microcode")

        if instr.dst not in (Reg.NONE, Reg.AL):
            raise HardwareBusError(f"DIV destination on HA_MUX must be AL, got {instr.dst}")

        dst = Reg.AL
        rem_reg = Reg.DL

        # Step 1: Combinatorial latch of inputs from HA_MUX and HB_MUX
        self._ha_mux.select(dst.value)
        self._inputs.hb_mux.select(instr.src.value)
        ha_val = self._inputs.ha_mux.read()
        hb_val = self._inputs.hb_mux.read()

        div_result = DivCore.div_core(a=ha_val, b=hb_val, signed=signed)

        if div_result.err:
            # Divide-by-zero aborts immediately without modifying registers (1 cycle via _writeback)
            self._outputs.block_res_sel.set(Reg.NONE.value)
            self._outputs.exec_done.set(1)
            self._wb_flags(div_result)
            self._writeback()
            return

        # Step 2: 30 compute cycles (Non-Restoring Division iterations)
        self._clock.tick(30)

        # Step 3: Cycle 31 - Writeback quotient to AL without status write
        self._outputs.status_wr_sel.set(0)
        self._outputs.block_res.set(div_result.quotient)
        self._outputs.block_res_sel.set(dst.value)
        self._writeback()

        # Step 4: Cycle 32 - Writeback remainder to DL and commit status flags
        self._outputs.block_res.set(div_result.remainder)
        self._outputs.block_res_sel.set(rem_reg.value)
        self._outputs.exec_done.set(1)
        self._wb_flags(div_result)
        self._writeback()



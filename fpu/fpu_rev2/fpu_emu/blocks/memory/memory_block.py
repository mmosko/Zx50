from typing import Callable, Union

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.blocks.memory.stack_adder import StackAdder
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register, StatusRegister
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.rom.fpu_const_map import FpuTable


@fpga_resource(
    approach="Memory controller, stack sequencer, scratch/user RAM, and unified LDC table ROM interface",
    luts=60,
    ffs=8,
    delay_ns=2.8,
    cycles=1,
    shared_unit="memory_block",
)
class MemoryBlock(FunctionalBlock):
    """
    Manipulates the math Stack, scratch memory, user memory, and constant ROMs.

    Physical EBR Allocation:
      DATA_RAM: EBR 0 (cascaded 1024 words x 32 bits):
        - Lower 256 words (0x000..0x0FF): RAM Space
          * Math Stack: words 0..127 (128 words x 32-bit)
          * Scratchpad RAM SCR[0..63]: words 128..191 (64 words x 32-bit)
          * User Word Storage USR[0..15]: words 192..207 (16 words x 32-bit)
          * Working Headroom: words 208..255 (48 words x 32-bit)
        - Upper 768 words (0x100..0x3FF): ROM Space
          * IEEE-754 Constants: words 256..319 (64 words x 32-bit)
          * Reserved Headroom: words 320..511 (192 words x 32-bit)
          * Trig & CORDIC Angles: words 512..639 (128 words x 32-bit)
          * Chebyshev Coefficients: words 640..767 (128 words x 32-bit)
          * Interleaved RECIP (low 16b) and SQRT (high 16b) seeds: words 768..1023 (256 words x 32-bit)
    """

    # DATA_RAM (EBR 0, 1024 words x 32-bit) Memory Map Bases
    MTH_BASE = 0x000  # Stack: words 0..127
    SCR_BASE = 0x080  # Scratchpad: words 128..191
    USR_BASE = 0x0C0  # User storage: words 192..207
    EXT_BASE = 0x0D0  # Free RAM headroom: words 208..255

    CNS_BASE = 0x100  # IEEE-754 Constants: words 256..319
    TRIG_BASE = 0x200  # Trig & CORDIC Angles: words 512..639
    CHEB_BASE = 0x280  # Chebyshev Coefficients: words 640..767
    SEEDS_BASE = 0x300  # Combined Seeds: words 768..1023

    def __init__(self,
                 name: str,
                 inputs: BlockInputs,
                 memory: Memory,
                 writeback: Callable,
                 clock: Clock,
                 sp_reg: Register):
        super().__init__(name, inputs, memory, writeback, clock)
        assert isinstance(inputs.ha_mux, Mux)
        self._ha_mux: Mux = inputs.ha_mux
        self._none_bus = Bus(name="none_bus", size_in_bits=4)
        self._upc_bus = Bus(name="upc_bus", size_in_bits=4)
        self._none_bus.set(Reg.NONE.value)

        self._sp = sp_reg
        self._stack_adder = StackAdder(sp_reg)
        self._status_shadow = StatusRegister(name=Reg.STATUS_SHADOW, size_in_bits=8, clock=clock)

    def execute(self):
        instr = MicroInstruction.from_register(self._inputs.instr)
        match instr.op:
            case MicroOp.PUSH:
                self._push(instr)
            case MicroOp.POP:
                self._pop(instr)
            case MicroOp.LDC:
                self._ldc(instr)
            case MicroOp.LDI:
                self._ldi(instr)
            case MicroOp.LD:
                self._ld(instr)
            case MicroOp.STO:
                self._sto(instr)
            case MicroOp.LDU:
                self._ldu(instr)
            case MicroOp.STU:
                self._stu(instr)
            case MicroOp.MOV:
                self._mov(instr)
            case MicroOp.SWAP:
                self._swap(instr)
            case MicroOp.SSAV:
                self._ssav(instr)
            case MicroOp.SRES:
                self._sres(instr)
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    STATUS_OVERFLOW_ERR_MASK = (1 << StatusFlag.OVERFLOW.value) | (1 << StatusFlag.ERR.value)
    STATUS_UNDERFLOW_ERR_MASK = (1 << StatusFlag.UNDERFLOW.value) | (1 << StatusFlag.ERR.value)

    def _push(self, instr: MicroInstruction) -> None:
        """push src to TOS"""
        assert (instr.op == MicroOp.PUSH)
        assert (instr.src is not Reg.NONE)
        if instr.is_w32():
            self._push32(instr)
        else:
            self._push64(instr)

    def _push32(self, instr: MicroInstruction) -> None:
        """push src to TOS"""
        assert instr.src is not Reg.NONE
        self._inputs.hb_mux.select(instr.src.value)
        self._inner_push32()
        self._outputs.exec_done.set(1)
        self._writeback()

    def _push64(self, instr: MicroInstruction) -> None:
        """push src to TOS, pushes low order bytes first"""
        assert instr.src is not Reg.NONE
        assert (instr.src.is_lo_half())
        self._inputs.hb_mux.select(instr.src.value)
        self._inner_push32()
        self._writeback()

        if self._outputs.res_status.read_int() != 0:
            # It was an error, we abort
            self._outputs.exec_done.set(1)
            return

        # select the HI register
        self._inputs.hb_mux.select(instr.src.value | 1)
        self._inner_push32()
        self._outputs.exec_done.set(1)
        self._writeback()

    def _inner_push32(self):
        value = self._inputs.hb_mux.read_int()

        # Set it up to calculate SP+1
        self._stack_adder.set_op(StackAdder.OP_INC)

        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(self.STATUS_OVERFLOW_ERR_MASK)

        if self._stack_adder.is_overflow:
            # Stack overflow: set VF and ERR, do not write memory or update SP
            self._outputs.res_status.set(self.STATUS_OVERFLOW_ERR_MASK)
            # calls to _writeback() done in caller
            return

        # No overflow: clear VF and ERR
        self._outputs.res_status.set(0)

        # 1 cycle to present address and data
        addr = self.MTH_BASE | (self._sp.read_int() & 0x7F)
        self._memory.write(0, addr, value & 0xFFFFFFFF)
        self._clock.tick()

        # Writeback the updated SP
        self._sp.write(self._stack_adder.read())
        # Calls to _writeback() are always done in the caller

    def _pop(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst"""
        assert instr.op == MicroOp.POP
        assert instr.dst is not Reg.NONE
        if instr.is_w32():
            self._pop32(instr)
        else:
            self._pop64(instr)

    def _pop32(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst (32-bit)"""
        assert instr.dst is not Reg.NONE
        self._inner_pop32()
        self._outputs.exec_done.set(1)
        if self._outputs.res_status.read_int() != 0:
            # Underflow error: commit UF/ERR without writing dst
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()

    def _pop64(self, instr: MicroInstruction) -> None:
        """Pops TOS to dst (64-bit), pops high order word first"""
        assert instr.dst is not Reg.NONE
        assert instr.dst.is_lo_half()

        # 1. Read HI word from TOS
        self._inner_pop32()
        if self._outputs.res_status.read_int() != 0:
            self._outputs.exec_done.set(1)
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value | 1)
        self._writeback()

        # 2. Read LO word from TOS
        self._inner_pop32()
        self._outputs.exec_done.set(1)
        if self._outputs.res_status.read_int() != 0:
            self._writeback()
            return

        self._outputs.block_res_sel.set(instr.dst.value)
        self._writeback()

    def _inner_pop32(self) -> None:
        # Set it up to calculate SP-1
        self._stack_adder.set_op(StackAdder.OP_DEC)

        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._outputs.status_wr_sel.set(self.STATUS_UNDERFLOW_ERR_MASK)

        if self._stack_adder.is_underflow:
            # Stack underflow: set UF and ERR, do not write memory or update SP
            self._outputs.res_status.set(self.STATUS_UNDERFLOW_ERR_MASK)
            return

        new_sp = self._stack_adder.read_int()

        # No underflow: clear UF and ERR
        self._outputs.res_status.set(0)
        self._clock.tick()

        # 1 cycle to present address and data
        addr = self.MTH_BASE | (new_sp & 0x7F)
        val = self._memory.read(0, addr)

        # Writeback the updated SP
        self._sp.write(self._stack_adder.read())

        # writeback the destination register
        self._outputs.block_res.set(val)


    def _ldc(self, instr: MicroInstruction) -> None:
        """Loads from constant/seed tables in DATA_RAM (EBR 0) using zero-cost bitwise OR addressing.

        Instruction format: LDC dst, tbl, addr
          - dst: Destination register (e.g. AL, AH, or even register AX for 64-bit W=1)
          - tbl (src): Table selector:
              * CONST: 0 (DATA_RAM, base 0x100, 64 words x 32-bit)
              * TRIG:  1 (DATA_RAM, base 0x200, 128 words x 32-bit)
              * CHEB:  2 (DATA_RAM, base 0x280, 128 words x 32-bit)
              * RECIP: 3 (DATA_RAM, base 0x300, 256 words x 16-bit low slice [15:0])
              * SQRT:  4 (DATA_RAM, base 0x300, 256 words x 16-bit high slice [31:16])
          - addr (src1 / imm):
              * If src1 is Reg.IMM or Reg.NONE: offset from HA_MUX(Reg.IMM)
              * Else: offset dynamically from HA_MUX(src1) (e.g. Reg.C, Reg.AL)
        """
        assert instr.op == MicroOp.LDC
        assert instr.dst is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)

        # 1. Resolve offset from HA_MUX
        if instr.src1 is not Reg.NONE and instr.src1 is not Reg.IMM:
            self._ha_mux.select(instr.src1.value)
        else:
            self._ha_mux.select(Reg.IMM.value)
        offset = self._ha_mux.read_int()

        # 2. Extract table selector
        tbl = instr.src

        if instr.is_w32():
            self._ldc_core(dst=instr.dst.value, tbl=tbl, offset=offset)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.dst.is_lo_half(), "64-bit LDC destination must be an even register (low half)"
            assert offset % 2 == 0, "64-bit LDC offset must be even"

            # 1. Read LO word from offset
            self._ldc_core(dst=instr.dst.value, tbl=tbl, offset=offset)
            self._writeback()

            # 2. Read HI word from offset + 1
            self._ldc_core(dst=instr.dst.value | 1, tbl=tbl, offset=offset + 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _ldc_core(self, dst: int, tbl: Union[FpuTable, int], offset: int) -> None:
        """Reads from DATA_RAM (EBR 0) constant/LUT tables using zero-cost bitwise OR addressing."""
        if tbl == FpuTable.CONST or tbl == 0:
            addr = self.CNS_BASE | (offset & 0x3F)
            val = self._memory.read(0, addr)
        elif tbl == FpuTable.TRIG or tbl == 1:
            addr = self.TRIG_BASE | (offset & 0x7F)
            val = self._memory.read(0, addr)
        elif tbl == FpuTable.CHEB or tbl == 2:
            addr = self.CHEB_BASE | (offset & 0x7F)
            val = self._memory.read(0, addr)
        elif tbl == FpuTable.RECIP or tbl == 3:
            addr = self.SEEDS_BASE | (offset & 0xFF)
            val = self._memory.read(0, addr) & 0xFFFF
        elif tbl == FpuTable.SQRT or tbl == 4:
            addr = self.SEEDS_BASE | (offset & 0xFF)
            val = (self._memory.read(0, addr) >> 16) & 0xFFFF
        else:
            raise HardwareBusError(f"Invalid LDC table selector: {tbl}")

        self._clock.tick()
        self._outputs.block_res.set(val)
        self._outputs.block_res_sel.set(dst)

    def _ldi(self, instr: MicroInstruction) -> None:
        """Loads 10-bit immediate into a register or modifies a single status flag.

        If dst == Reg.NONE:
            LDI <flag>, imm
            Sets or clears the specified StatusFlag to (imm & 1) using status write mask.
        If dst != Reg.NONE:
            LDI <reg>, imm
            Loads 10-bit unsigned immediate into register dst (zero-extended).
        """
        assert instr.op == MicroOp.LDI
        self._inputs.hb_mux.select(Reg.IMM.value)
        imm = self._inputs.hb_mux.read_int()

        if instr.dst is Reg.NONE:
            flag = instr.flag
            bit_val = imm & 1
            mask = 1 << flag.value

            self._outputs.block_res.set(0)
            self._outputs.block_res_sel.set(Reg.NONE)
            self._outputs.res_status.set(bit_val << flag.value)
            self._outputs.status_wr_sel.set(mask)
            self._outputs.exec_done.set(1)
            self._writeback()
        elif instr.is_w32():
            self._outputs.block_res.set(imm)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.res_status.set(0)
            self._outputs.status_wr_sel.set(0)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.dst.is_lo_half()
            self._outputs.block_res.set(imm)
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.res_status.set(0)
            self._outputs.status_wr_sel.set(0)
            self._writeback()

            self._clock.tick()
            self._outputs.block_res.set(0)
            self._outputs.block_res_sel.set(instr.dst.value | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _ld(self, instr: MicroInstruction) -> None:
        """Loads 32-bit or 64-bit from scratchpad RAM SCR[addr]."""
        assert instr.op == MicroOp.LD
        assert instr.dst is not Reg.NONE
        assert instr.src1 is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)

        self._ha_mux.select(instr.src1.value)
        addr = self._ha_mux.read_int()

        if instr.is_w32():
            self._ld_core(dst=instr.dst.value, addr=addr)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.dst.is_lo_half()
            assert addr % 2 == 0, "64-bit LD must use even base"

            # 1. Read LO word from addr
            self._ld_core(dst=instr.dst.value, addr=addr)
            self._writeback()

            # 2. Read HI word from addr + 1
            self._ld_core(dst=instr.dst.value | 1, addr=addr | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _ld_core(self, dst: int, addr: int):
        ram_addr = self.SCR_BASE | (addr & 0x3F)
        val = self._memory.read(0, ram_addr)
        self._clock.tick()
        self._outputs.block_res.set(val)
        self._outputs.block_res_sel.set(dst)

    def _sto(self, instr: MicroInstruction) -> None:
        """Stores 32-bit or 64-bit from register src into scratchpad RAM SCR[addr]."""
        assert instr.op == MicroOp.STO
        assert instr.src is not Reg.NONE
        assert instr.src1 is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)

        self._ha_mux.select(instr.src1.value)
        addr = self._ha_mux.read_int()

        if instr.is_w32():
            self._sto_core(src=instr.src.value, addr=addr)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.src.is_lo_half()
            assert addr % 2 == 0, "64-bit STO must use even base"

            # 1. Write LO word to addr
            self._sto_core(src=instr.src.value, addr=addr)
            self._writeback()

            # 2. Write HI word to addr + 1
            self._sto_core(src=instr.src.value | 1, addr=addr | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _sto_core(self, src: int, addr: int):
        self._inputs.hb_mux.select(src)
        val = self._inputs.hb_mux.read_int()
        ram_addr = self.SCR_BASE | (addr & 0x3F)
        self._memory.write(0, ram_addr, val & 0xFFFFFFFF)
        self._clock.tick()

    def _ldu(self, instr: MicroInstruction) -> None:
        """Loads 32-bit or 64-bit from user buffer USR[imm] in DATA_RAM."""
        assert instr.op == MicroOp.LDU
        assert instr.dst is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)

        self._ha_mux.select(Reg.IMM.value)
        imm = self._ha_mux.read_int()

        if instr.is_w32():
            self._ldu_core(dst=instr.dst.value, addr=imm)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.dst.is_lo_half()
            assert imm % 2 == 0, "64-bit LDU must use even base"

            # 1. Read LO word from addr
            self._ldu_core(dst=instr.dst.value, addr=imm)
            self._writeback()

            # 2. Read HI word from addr + 1
            self._ldu_core(dst=instr.dst.value | 1, addr=imm | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _ldu_core(self, dst: int, addr: int):
        ram_addr = self.USR_BASE | (addr & 0x0F)
        val = self._memory.read(0, ram_addr)
        self._clock.tick()
        self._outputs.block_res.set(val)
        self._outputs.block_res_sel.set(dst)

    def _stu(self, instr: MicroInstruction) -> None:
        """Stores 32-bit or 64-bit from register src into user buffer USR[imm] in DATA_RAM."""
        assert instr.op == MicroOp.STU
        assert instr.src is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)

        self._ha_mux.select(Reg.IMM.value)
        imm = self._ha_mux.read_int()

        if instr.is_w32():
            self._stu_core(src=instr.src.value, addr=imm)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.src.is_lo_half()
            assert imm % 2 == 0, "64-bit STU must use even base"

            # 1. Write LO word to addr
            self._stu_core(src=instr.src.value, addr=imm)
            self._writeback()

            # 2. Write HI word to addr + 1
            self._stu_core(src=instr.src.value | 1, addr=imm | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _stu_core(self, src: int, addr: int):
        self._inputs.hb_mux.select(src)
        val = self._inputs.hb_mux.read_int()
        ram_addr = self.USR_BASE | (addr & 0x0F)
        self._memory.write(0, ram_addr, val & 0xFFFFFFFF)
        self._clock.tick()

    def _mov(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.MOV)
        assert (instr.src is not Reg.NONE)
        assert (instr.dst is not Reg.NONE)

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)

        if instr.is_w32():
            self._inputs.hb_mux.select(instr.src.value)
            self._outputs.block_res.set(self._inputs.hb_mux.read_int())
            self._outputs.block_res_sel.set(instr.dst.value)
            self._outputs.exec_done.set(1)
            self._writeback()
        else:
            assert instr.src.is_lo_half()
            assert instr.dst.is_lo_half()
            # 1. Transfer LO word
            self._inputs.hb_mux.select(instr.src.value)
            self._outputs.block_res.set(self._inputs.hb_mux.read_int())
            self._outputs.block_res_sel.set(instr.dst.value)
            self._writeback()

            # 2. Transfer HI word
            self._inputs.hb_mux.select(instr.src.value | 1)
            self._outputs.block_res.set(self._inputs.hb_mux.read_int())
            self._outputs.block_res_sel.set(instr.dst.value | 1)
            self._outputs.exec_done.set(1)
            self._writeback()

    def _swap(self, instr: MicroInstruction) -> None:
        """Exchanges the contents of two 32-bit registers using FL as an intermediary.

        Execution sequence (3 clock cycles):
          Cycle 1: Read src from HB_MUX, write to intermediary register (FL, or DL if FL is operand)
          Cycle 2: Read dst from HB_MUX, write to src
          Cycle 3: Read intermediary from HB_MUX, write to dst, assert exec_done
        """
        assert instr.op == MicroOp.SWAP
        assert instr.src is not Reg.NONE
        assert instr.dst is not Reg.NONE

        self._outputs.status_wr_sel.set(0)
        self._outputs.res_status.set(0)

        if instr.dst == instr.src:
            self._outputs.block_res_sel.set(Reg.NONE.value)
            self._outputs.exec_done.set(1)
            self._writeback()
            return

        # Use FL as intermediary unless FL is an operand, in which case use DL
        temp_reg = Reg.DL if Reg.FL in (instr.dst, instr.src) else Reg.FL

        # Cycle 1: temp_reg <- src
        self._inputs.hb_mux.select(instr.src.value)
        self._outputs.block_res.set(self._inputs.hb_mux.read_int())
        self._outputs.block_res_sel.set(temp_reg.value)
        self._outputs.exec_done.set(0)
        self._writeback()

        # Cycle 2: src <- dst
        self._inputs.hb_mux.select(instr.dst.value)
        self._outputs.block_res.set(self._inputs.hb_mux.read_int())
        self._outputs.block_res_sel.set(instr.src.value)
        self._outputs.exec_done.set(0)
        self._writeback()

        # Cycle 3: dst <- temp_reg
        self._inputs.hb_mux.select(temp_reg.value)
        self._outputs.block_res.set(self._inputs.hb_mux.read_int())
        self._outputs.block_res_sel.set(instr.dst.value)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _ssav(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.SSAV)
        status = self._inputs.status.read_int()
        self._status_shadow.write(status)
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE)
        self._outputs.status_wr_sel.set(0)
        self._outputs.exec_done.set(1)
        self._writeback()

    def _sres(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.SRES)
        status = self._status_shadow.read_int()
        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE)
        self._outputs.res_status.set(status)
        # Does not write BUSY (bit 7) or ERR (bit 1)
        self._outputs.status_wr_sel.set(0x7D)
        self._outputs.exec_done.set(1)
        self._writeback()


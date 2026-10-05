from typing import Callable, Optional

from fpu_emu.blocks.control.count_adder import CountAdder
from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.blocks.memory.stack_adder import StackAdder
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import HardwareBusError, StatusFlag
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp


class MemoryBlock(FunctionalBlock):
    """
    Manipulates the math Stack, the scratch memory and the user memory.

    EBR 0 & EBR 1 (paired 512 words x 36 bits)
      - Hardware Math Stack (128 words x 32-bit)
      - Scratchpad RAM SCR[0..63] (64 x 32-bit)
      - User Word Storage (16 words x 32-bit)
      - Reserved / Working Headroom (304 words)
    """

    # TODO: For these to be pure prefixes (not adds), we need the prefix to align at 7 bits, so
    # we get 2 prefix bits
    MTH_BASE = 0b0_0000_0000
    SCR_BASE = 0b0_1000_0000
    USR_BASE = 0b1_0000_0000
    EXT_BASE = 0b1_1000_0000

    def __init__(self,
                 name: str,
                 inputs: BlockInputs,
                 memory: Memory,
                 writeback: Callable,
                 clock: Clock,
                 sp_reg: Register):
        super().__init__(name, inputs, memory, writeback, clock)
        self._none_bus = Bus(name="none_bus", size_in_bits=4)
        self._upc_bus = Bus(name="upc_bus", size_in_bits=4)
        self._none_bus.set(Reg.NONE.value)

        self._sp = sp_reg
        self._stack_adder = StackAdder(sp_reg)

    # | PUSH src         | 0b100_000 | 0/1   | TOS     | n/a    | src    | `TOS <- src`, sp <- sp + W + 1     | sets VF, ERR (on stack overflow)      |
    # | POP dst          | 0b100_001 | 0/1   | dst     | n/a    | TOS    | `dst <- TOS`, sp <- sp - (W+1)     | sets UF, ERR (on stack underflow)     |
    # | LDC dst, addr    | 0b100_010 | 0/1   | dst     | IMM    | n/a    | `dst <- CONST_ADDR + [addr]`       | none (flags unaffected)               |
    # | LDI dst, imm     | 0b100_011 | 0/1   | dst     | IMM    | n/a    | `dst <- imm`                       | none (flags unaffected)               |
    # | LD  dst, addr    | 0b100_100 | 0/1   | dst     | IMM    | n/a    | `dst <- SCR_ADDR + [addr]`         | none (flags unaffected)               |
    # | ST  addr, src    | 0b100_101 | 0/1   | IMM     | n/a    | src    | `SCR_ADDR + [addr] <- src`         | none (flags unaffected)               |
    # | LDU dst, addr    | 0b101_000 | 0/1   | dst     | IMM    | n/a    | `dst <- USER_ADDR + [addr]`        | none (flags unaffected)               |
    # | STU addr, src    | 0b101_001 | 0/1   | dst     | IMM    | n/a    | `USER_ADDR + [addr] <- src`        | none (flags unaffected)               |
    # | MOV dst, src     | 0b100_110 | 0/1   | dst     | n/a    | src    | `dst <- src`                       | none (flags unaffected)               |
    # | SWAP dst, src    | 0b100_111 | 0/1   | dst     | n/a    | src    | `F_ <- src, src <- dst, dst <- F_` | none (flags unaffected)               |

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
            case _:
                raise HardwareBusError(f"Unsupported opcode: {instr.op}")

    def _push(self, instr: MicroInstruction) -> None:
        """
        push src to TOS
        :param instr:
        :return:
        """
        assert (instr.op == MicroOp.PUSH)
        assert (instr.src is not None)

        self._inputs.hb_mux.select(instr.src.value)
        value = self._inputs.hb_mux.read_int()
        # This is a bit prefix, not an add
        addr = self.MTH_BASE | self._sp.read_int()

        # Set it up to calculate SP+1
        self._stack_adder.set_op(StackAdder.OP_INC)

        # 1 cycle to present address and data
        self._memory.write(0, addr, value & 0xFFFF)
        self._memory.write(1, addr, (value >> 16) & 0xFFFF)
        self._clock.tick()

        self._outputs.exec_done.set(1)
        # 1 cycle for write to complete

        self._outputs.block_res.set(0)
        self._outputs.block_res_sel.set(Reg.NONE.value)
        self._clock.tick()

        # N.B.: No call to _writeback, the UPC is handled by the upc_mux

    def _pop(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.POP)
        raise NotImplementedError

    def _ldc(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDC)
        raise NotImplementedError

    def _ldi(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDI)
        raise NotImplementedError

    def _ld(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LD)
        raise NotImplementedError

    def _sto(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.STO)
        raise NotImplementedError

    def _ldu(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.LDU)
        raise NotImplementedError

    def _stu(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.STU)
        raise NotImplementedError

    def _mov(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.MOV)
        raise NotImplementedError

    def _swap(self, instr: MicroInstruction) -> None:
        assert (instr.op == MicroOp.SWAP)
        raise NotImplementedError

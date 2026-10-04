"""Command Dispatcher and Micro-sequencer execution engine."""

from typing import Callable, List

from fpu_emu.blocks.functional_block import FunctionalBlock
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.register import Register
from fpu_emu.hardware.registers import StatusFlag
from fpu_emu.micro_code import MicroCode
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode


class Dispatcher:
    """Dispatches user opcodes and executes microcode instruction streams."""

    def __init__(self, blocks: List[FunctionalBlock], upc: Register, status: Register, sp: Register, osp: Register,
                 instr_reg: Register, imm_reg: Register,
                 memory: Memory, clock: Clock):
        self._blocks = blocks,
        self._memory = memory
        self._clock = clock
        self._upc = upc
        # we are cheating for a bit with a local pc int
        self._pc = 0
        self._sp = sp
        self._osp = osp
        self._instr_reg = instr_reg
        self._imm_reg = imm_reg
        self._status = status
        self._halted: bool = False
        self._batch_mode: bool = False
        self._blocking_mode: bool = True
        self._zero = bytes(0)

    @property
    def batch_mode(self) -> bool:
        """Returns True if FPU is in BATCH execution mode."""
        return self._batch_mode

    @property
    def blocking_mode(self) -> bool:
        """Returns True if FPU asserts ~BWAIT on busy (blocking mode)."""
        return self._blocking_mode

    @property
    def bwait_n(self) -> bool:
        """Active-low ~BWAIT line to host CPU: 0 (False) = hold CPU, 1 (True) = ready."""
        is_busy = self._status.is_bit_set(StatusFlag.BUSY.value)
        # BWAIT_N is driven low (0) when BLOCKING and BUSY
        return not (self._blocking_mode and is_busy)

    def execute(self, user_opcode: UserOpcode):
        """Executes a user opcode or enqueues it if in batch mode.

        :param user_opcode: UserOpcode command to execute.
        """
        # 1-cycle command dispatch overhead
        self._clock.tick(1)

        # Handle mode & control commands directly
        if user_opcode == UserOpcode.SET_BATCH:
            self._batch_mode = True
            return
        elif user_opcode == UserOpcode.SET_IMMEDIATE:
            self._batch_mode = False
            return
        elif user_opcode == UserOpcode.SET_BLOCKING:
            self._blocking_mode = True
            return
        elif user_opcode == UserOpcode.SET_NONBLOCKING:
            self._blocking_mode = False
            return
        elif user_opcode == UserOpcode.CLEAR_STACK:
            self._sp.write(b'\x00')
            self._osp.write(b'\x00')
            return
        elif user_opcode == UserOpcode.RESET:
            self._batch_mode = False
            self._blocking_mode = True
            raise NotImplementedError()
            return
        elif user_opcode == UserOpcode.EXEC_BATCH:
            raise NotImplementedError()
            # self._execute_batch()
            # return

        # If in batch mode, enqueue into command queue
        # if self._batch_mode:
        #     self._enqueue_command(user_opcode)
        #     return

        # Immediate computational execution
        self._execute_immediate(user_opcode)

    def _execute_immediate(self, user_opcode: UserOpcode):
        """Executes a single computational opcode immediately with BUSY management."""
        self._status.set_bit(StatusFlag.BUSY.value, True)
        try:
            # TODO: We should burn the microcode into the EBR, but for now it is much easier to
            # be writing and reading micro instructions.
            ucode = MicroCode.get(user_opcode)
            self._run(ucode)
        finally:
            self._status.set_bit(StatusFlag.BUSY.value, False)

    # def _execute_batch(self):
    #     """Executes all queued commands in RAM sequentially with BUSY held high."""
    #     self._hw.reg.set_flag(StatusFlag.BUSY, True)
    #     try:
    #         osp = self._hw.reg.osp
    #         for i in range(osp):
    #             opcode_val = self._hw.mem[CMD_STACK_BASE + i]
    #             try:
    #                 opcode = UserOpcode(opcode_val)
    #                 ucode = MicroCode.get(opcode)
    #                 self._run(ucode)
    #                 # Halt batch early if error occurred
    #                 if self._hw.reg.get_flag(StatusFlag.ERR):
    #                     break
    #             except (ValueError, NotImplementedError):
    #                 self._hw.reg.set_flag(StatusFlag.ERR, True)
    #                 break
    #         # Reset command queue pointer
    #         self._hw.reg.osp = 0
    #     finally:
    #         self._hw.reg.set_flag(StatusFlag.BUSY, False)

    # def _enqueue_command(self, user_opcode: UserOpcode):
    #     """Enqueues a user opcode into SysMEM command queue (0x0340..0x035F)."""
    #     self._hw.clock.tick(1)
    #     osp = self._hw.reg.osp
    #     if osp >= CMD_STACK_SIZE:
    #         self._hw.reg.set_flag(StatusFlag.OVERFLOW, True)
    #         self._hw.reg.set_flag(StatusFlag.ERR, True)
    #         return
    #
    #     self._hw.mem[CMD_STACK_BASE + osp] = user_opcode.value
    #     self._hw.reg.osp = osp + 1

    def _run(self, microcode: List[MicroInstruction]):
        """Micro-sequencer execution loop.

        Fetches each micro-instruction (1 tick), then executes it.
        """
        saved_pc, saved_halted = self._pc, self._halted

        # N.B. Using the micro_code dictionary, we only use the UPC from 0:N words
        self._upc.write(b'0x00')
        self._halted = False

        # TODO: for now we are cheating with a Python pc
        self._pc = 0
        try:
            while not self._halted and self._pc < len(microcode):
                # 1 cycle micro-instruction fetch
                self._clock.tick(1)
                instr = microcode[self._pc]
                self._pc += 1
                instr.to_register(self._instr_reg, self._imm_reg)

                block_num = instr.op.value >> 3 & 0x07

                # TODO: Some blocks (i.e. control) will modify the PC.  We really need to switch to using
                # self._upc register rather than self._pc
                self._blocks[block_num].execute()

        finally:
            self._pc, self._halted = saved_pc, saved_halted

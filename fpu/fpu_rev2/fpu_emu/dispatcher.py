"""Command Dispatcher and Micro-sequencer execution engine."""

from typing import List

from fpu_emu.blocks.functional_block import FunctionalBlock
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.register import Register, StatusRegister
from fpu_emu.hardware.registers import StatusFlag, UpcOverflowError
from fpu_emu.micro_code import MicroCode
from fpu_emu.micro_instruction import MicroInstruction
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.user_opcodes import UserOpcode
from fpu_emu.writeback_mux import WritebackMux


class Dispatcher:
    """Dispatches user opcodes and executes microcode instruction streams."""

    def __init__(self,
                 blocks: List[FunctionalBlock],
                 upc: Register,
                 status: StatusRegister,
                 sp: Register,
                 osp: Register,
                 instr_reg: Register,
                 imm_reg: Register,
                 memory: Memory,
                 clock: Clock,
                 writeback_mux: WritebackMux,
                 upc_mux: Mux):
        self._blocks = blocks
        self._memory = memory
        self._clock = clock
        self._upc = upc
        self._upc_mux = upc_mux
        self._sp = sp
        self._osp = osp
        self._instr_reg = instr_reg
        self._imm_reg = imm_reg
        self._status = status
        self._halted: bool = False
        self._batch_mode: bool = False
        self._blocking_mode: bool = True
        self._zero = bytes(0)
        self._writeback_mux = writeback_mux

    @property
    def upc(self) -> int:
        """Returns current UPC register value."""
        return self._upc.read_int()

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
        is_busy = self._status.is_bit_set(StatusFlag.BUSY)
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
            self._sp.write(0)
            self._osp.write(0)
            return
        elif user_opcode == UserOpcode.RESET:
            self._batch_mode = False
            self._blocking_mode = True
            raise NotImplementedError()
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
        self._status.set_bit(StatusFlag.BUSY, True)
        try:
            # TODO: We should burn the microcode into the EBR, but for now it is much easier to
            # be writing and reading micro instructions.
            ucode = MicroCode.get(user_opcode)

            # In the FPGA, this needs to initialize the UPC to the full memory address of the microcode
            # instruction.  For ease of use in Python, we use a small array per User opcode, so we always
            # use 0
            self._upc.write(0)
            self._run(ucode)
        finally:
            if self._status.is_bit_set(StatusFlag.BUSY):
                self._status.set_bit(StatusFlag.BUSY, False)

    def _run(self, microcode: List[MicroInstruction]):
        """Micro-sequencer execution loop.

        Fetches each micro-instruction (pipelined), then executes it.
        Cycle T0 (pipeline prime): fetch _upc, calculate _upc_next via UpcAdder,
        latch instruction into reg.instr on clock edge, and latch upc_next into _upc.
        Cycle T1..TN: execute reg.instr, update UPC from upc_mux on writeback edge,
        and latch next fetched instruction into reg.instr.
        """
        if not microcode:
            raise NotImplementedError()

        saved_halted = self._halted
        self._halted = False

        # Read initial UPC (defaults to 0 unless set by caller)
        current_upc = self._upc.read_int()

        # Cycle T0: Fetch instruction at _upc, calculate _upc_next
        fetch_instr = microcode[current_upc]

        # The UpcAdder is always executing in parallel
        self._upc_mux.select(0)
        upc_next = self._upc_mux.read_int()
        if upc_next & 0x400 > 0:
            self._status.set_bit(StatusFlag.ERR, True)
            raise UpcOverflowError("UPC overflow/carry during fetch")

        # T0 clock tick to present result to reg.instr / imm_reg on T1
        self._clock.tick(1)
        fetch_instr.to_register(self._instr_reg, self._imm_reg)
        self._upc.write(upc_next & 0x3FF)

        nop_instr = MicroInstruction(op=MicroOp.NOP)
        try:
            while not self._halted:
                # Read and decode instruction from reg.instr
                instr = MicroInstruction.from_register(self._instr_reg)
                block_num = (instr.op.value >> 3) & 0x07
                self._writeback_mux.set_block(block_num)

                # Execute current instruction
                # This advances the clock for edge-triggered writeback (1 tick per instruction)
                self._blocks[block_num].execute()

                # Reading the UPC mux happens after execute, as it might need the result of a JUMP address
                if block_num == 3 and self._blocks[3].outputs.block_res_sel.read_int() == Reg.UPC.value:
                    # The JUMP writeback
                    self._upc_mux.select(1)
                    is_jump = True
                else:
                    # The adder output
                    self._upc_mux.select(0)
                    is_jump = False

                upc_next = self._upc_mux.read_int()
                if upc_next & 0x400 > 0:
                    self._status.set_bit(StatusFlag.ERR, True)
                    raise UpcOverflowError("UPC overflow/carry during fetch")

                if is_jump:
                    branch_target = upc_next & 0x3FF
                    if self._halted or branch_target >= len(microcode):
                        break
                    # Branch taken:
                    # 1. UPC <= branch_target (from UPC_MUX input 1, no second adder)
                    self._upc.write(branch_target)
                    # 2. Insert NOP bubble to flush the prefetched instruction
                    nop_instr.to_register(self._instr_reg, self._imm_reg)
                else:
                    current_upc = self._upc.read_int()
                    if self._halted or current_upc >= len(microcode):
                        break
                    # Latch fetched instruction into reg.instr
                    fetch_instr = microcode[current_upc]
                    fetch_instr.to_register(self._instr_reg, self._imm_reg)
                    # UPC <= UPC + 1 (from UpcAdder)
                    self._upc.write(upc_next & 0x3FF)

        finally:
            self._halted = saved_halted


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

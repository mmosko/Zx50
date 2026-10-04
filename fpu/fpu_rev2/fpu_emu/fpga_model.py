"""Top-level FPGA system model."""
from fpu_emu.blocks.adder.adder_block import AdderBlock
from fpu_emu.blocks.adder.empty_block import EmptyBlock
from fpu_emu.blocks.functional_block import BlockInputs
from fpu_emu.dispatcher import Dispatcher
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import Registers, HardwareBusError, StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.writeback_mux import WritebackMux


class FpgaModel:
    """Complete FPGA system model combining Hardware, ALU, Sequencer, and Host Interface."""

    def __init__(self, rom: Rom):
        self.clock = Clock()
        self.rom = rom
        self.memory = Memory(
            rom_blocks=[None, None, None, None, None, None, None, None],
            clock = self.clock
        )
        self.reg_file = Registers(clock=self.clock)

        self.ha_mux = Mux(name="ha", inputs=[
            self.reg_file.al,
            self.reg_file.ah,
            self.reg_file.ea,
            self.reg_file.eb,
            self.reg_file.imm,
            self.reg_file.c
        ])

        self.hb_mux = Mux(name="hb", inputs=[
            self.reg_file.al,
            self.reg_file.ah,
            self.reg_file.ea,
            self.reg_file.eb,
            self.reg_file.imm,
            self.reg_file.c,
            self.reg_file.bl,
            self.reg_file.bh,
            self.reg_file.dl,
            self.reg_file.dh,
            self.reg_file.fl,
            self.reg_file.fh,
        ])

        self.inputs = BlockInputs(
            ha_mux = self.ha_mux,
            hb_mux = self.hb_mux,
            status = self.reg_file.status,
            instr = self.reg_file.instr,
            exec_ready = self.reg_file.exec_ready
        )

        self.adder = AdderBlock(
            name="adder",
            inputs=self.inputs,
            memory=self.memory,
            writeback=self._writeback,
            clock=self.clock
        )

        self.empty_block = EmptyBlock(
            name="empty",
            inputs=self.inputs,
            memory=self.memory,
            writeback=self._writeback,
            clock=self.clock
        )

        # This is not hardware, but our map of the opcode block to the function
        self.blocks = [
            self.adder,         # 0
            self.adder,         # 1
            self.empty_block,   # 2
            self.empty_block,   # 3
            self.empty_block    # 4
        ]

        self.writeback_mux = WritebackMux(blocks=self.blocks)

        self.dispatcher = Dispatcher(
            blocks=self.blocks,
            clock=self.clock,
            upc=self.reg_file.upc,
            status=self.reg_file.status,
            sp=self.reg_file.sp,
            osp=self.reg_file.osp,
            instr_reg=self.reg_file.instr,
            imm_reg=self.reg_file.imm,
            memory=self.memory,
            writeback_mux=self.writeback_mux
        )

    def _writeback(self):
        """
        This block monitors the EXEC_WB flag.  When it is asserted, we use the output blocks to writeback to
        the register file.

        Simply calling this funciton is the equivalent of pulsing EXEC_WB and letting a tick go by.

        The dispatcher is responsible for setting the MUX selects
        :return:
        """
        self.clock.tick()
        dst: int = self.writeback_mux.res_sel_mux.read_int()
        res: bytes = self.writeback_mux.res_mux.read()

        # this is really just trigger a single write line, as all the register inputs are tied
        # to the res_mux output
        match dst:
            case Reg.AL:
                self.reg_file.al.write(res)
            case Reg.AH:
                self.reg_file.ah.write(res)
            case Reg.BL:
                self.reg_file.bl.write(res)
            case Reg.BH:
                self.reg_file.bh.write(res)
            case Reg.DL:
                self.reg_file.dl.write(res)
            case Reg.DH:
                self.reg_file.dh.write(res)
            case Reg.FL:
                self.reg_file.fl.write(res)
            case Reg.FH:
                self.reg_file.fh.write(res)
            case Reg.EA:
                self.reg_file.ea.write(res)
            case Reg.EB:
                self.reg_file.eb.write(res)
            case _:
                raise HardwareBusError(f"Unsupported dst register {dst}")

        # Writeback the status register
        status_byte: int = self.writeback_mux.status_mux.read_int()
        status_sel: int = self.writeback_mux.status_wr_sel_mux.read_int()
        if status_sel & StatusFlag.ZERO.value:
            flag: bool = status_byte & StatusFlag.ZERO.value != 0
            self.reg_file.status.set_bit(StatusFlag.ZERO, flag)
        if status_sel & StatusFlag.SIGN.value:
            flag: bool = status_byte & StatusFlag.SIGN.value != 0
            self.reg_file.status.set_bit(StatusFlag.SIGN, flag)
        if status_sel & StatusFlag.CARRY.value:
            flag: bool = status_byte & StatusFlag.CARRY.value != 0
            self.reg_file.status.set_bit(StatusFlag.CARRY, flag)
        if status_sel & StatusFlag.OVERFLOW.value:
            flag: bool = status_byte & StatusFlag.OVERFLOW.value != 0
            self.reg_file.status.set_bit(StatusFlag.OVERFLOW, flag)
        if status_sel & StatusFlag.UNDERFLOW.value:
            flag: bool = status_byte & StatusFlag.UNDERFLOW.value != 0
            self.reg_file.status.set_bit(StatusFlag.UNDERFLOW, flag)
        if status_sel & StatusFlag.ERR.value:
            flag: bool = status_byte & StatusFlag.ERR.value != 0
            self.reg_file.status.set_bit(StatusFlag.ERR, flag)


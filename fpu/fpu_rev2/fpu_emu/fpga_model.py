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

        # Map of the opcode block (0..7) to functional blocks
        self.blocks = [
            self.adder,         # 0 (0b000): Arithmetic / Adder
            self.adder,         # 1 (0b001): Math / Float / Divider
            self.empty_block,   # 2 (0b010): Logic
            self.empty_block,   # 3 (0b011): Control
            self.empty_block,   # 4 (0b100): Memory / Stack
            self.empty_block,   # 5 (0b101): Memory / Storage
            self.empty_block,   # 6 (0b110): Shifter / LZC
            self.empty_block,   # 7 (0b111): Reserved / Empty
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
        reg_map = {
            Reg.AL.value: self.reg_file.al,
            Reg.AH.value: self.reg_file.ah,
            Reg.BL.value: self.reg_file.bl,
            Reg.BH.value: self.reg_file.bh,
            Reg.DL.value: self.reg_file.dl,
            Reg.DH.value: self.reg_file.dh,
            Reg.FL.value: self.reg_file.fl,
            Reg.FH.value: self.reg_file.fh,
            Reg.EA.value: self.reg_file.ea,
            Reg.EB.value: self.reg_file.eb,
        }
        if dst in reg_map:
            reg_map[dst].write(res)
        elif dst == Reg.C:
            self.reg_file.c.write(res[:1])
        elif dst in (Reg.NONE, Reg.STATUS):
            pass
        else:
            raise HardwareBusError(f"Unsupported dst register {dst}")

        # Writeback the status register using proper bit masks
        status_byte: int = self.writeback_mux.status_mux.read_int()
        status_sel: int = self.writeback_mux.status_wr_sel_mux.read_int()
        for flag in StatusFlag:
            mask = 1 << flag.value
            if status_sel & mask:
                bit_val: bool = (status_byte & mask) != 0
                self.reg_file.status.set_bit(flag, bit_val)


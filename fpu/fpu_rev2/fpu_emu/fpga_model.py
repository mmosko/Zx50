"""Top-level FPGA system model."""
from fpu_emu.blocks.adder.adder_block import AdderBlock
from fpu_emu.blocks.control.control_block import ControlBlock
from fpu_emu.blocks.empty_block import EmptyBlock
from fpu_emu.blocks.functional_block import BlockInputs
from fpu_emu.blocks.memory.memory_block import MemoryBlock
from fpu_emu.dispatcher import Dispatcher
from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.bus_pad import BusPad
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg
from fpu_emu.hardware.registers import Registers, HardwareBusError, StatusFlag
from fpu_emu.hardware.rom import Rom
from fpu_emu.hardware.upc_adder import UpcAdder
from fpu_emu.writeback_mux import WritebackMux


@fpga_resource(
    approach="Datapath operand multiplexers (HA_MUX 6:1 32b, HB_MUX 12:1 32b, UPC_MUX 2:1 11b)",
    luts=299,
    delay_ns=2.8,
    cycles=1,
    shared_unit="datapath_muxes",
)
class DatapathMuxes:
    """Encloses top-level datapath routing multiplexers (HA_MUX, HB_MUX)."""

    def __init__(self, reg_file: Registers):
        self.ha_mux = Mux(name="ha", inputs=[
            reg_file.al,
            reg_file.ah,
            BusPad(reg_file.ea, 32, signed=True),
            BusPad(reg_file.eb, 32, signed=True),
            BusPad(reg_file.imm, 32),
            BusPad(reg_file.c, 32),
        ])

        self.hb_mux = Mux(name="hb", inputs=[
            reg_file.al,
            reg_file.ah,
            BusPad(reg_file.ea, 32, signed=True),
            BusPad(reg_file.eb, 32, signed=True),
            BusPad(reg_file.imm, 32),
            BusPad(reg_file.c, 32),
            reg_file.bl,
            reg_file.bh,
            reg_file.dl,
            reg_file.dh,
            reg_file.fl,
            reg_file.fh,
        ])


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
        self.datapath_muxes = DatapathMuxes(self.reg_file)
        self.ha_mux = self.datapath_muxes.ha_mux
        self.hb_mux = self.datapath_muxes.hb_mux

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

        self.control_inputs = BlockInputs(
            # HA hardwired to UPC register output
            ha_mux = self.reg_file.upc,
            hb_mux = self.hb_mux,
            status = self.reg_file.status,
            instr = self.reg_file.instr,
            exec_ready = self.reg_file.exec_ready
        )

        self.control_block = ControlBlock(
            name="control",
            inputs=self.control_inputs,
            memory=self.memory,
            writeback=self._writeback,
            clock=self.clock,
            c_reg=self.reg_file.c
        )

        self.memory_inputs = BlockInputs(
            ha_mux=self.ha_mux,
            hb_mux=self.hb_mux,
            status=self.reg_file.status,
            instr=self.reg_file.instr,
            exec_ready=self.reg_file.exec_ready,
        )

        self.memory_block = MemoryBlock(
            name="memory",
            inputs=self.memory_inputs,
            memory=self.memory,
            writeback=self._writeback,
            clock=self.clock,
            sp_reg=self.reg_file.sp,
        )

        # Map of the opcode block (0..7) to functional blocks
        self.blocks = [
            self.adder,         # 0 (0b000): Arithmetic / Adder
            self.adder,         # 1 (0b001): Math / Float / Divider
            self.empty_block,   # 2 (0b010): Logic
            self.control_block,   # 3 (0b011): Control
            self.memory_block,  # 4 (0b100): Memory / Stack
            self.memory_block,  # 5 (0b101): Memory / Storage
            self.empty_block,   # 6 (0b110): Shifter / LZC
            self.empty_block,   # 7 (0b111): Reserved / Empty
        ]

        self.writeback_mux = WritebackMux(blocks=self.blocks)
        self.upc_adder = UpcAdder(self.reg_file.upc)

        # The UPC takes its value either from the pre-calculated +1 or from the result
        # of a control JUMP.
        # Bit 11 is the overflow (carray) bit
        self.upc_mux = Mux(name="upc", inputs=[
            # 11 bits
            self.upc_adder,
            # 32-bits, but we only use the bottom 11
            self.control_block.outputs.block_res
        ])

        self.dispatcher = Dispatcher(
            blocks=self.blocks,
            clock=self.clock,
            upc=self.reg_file.upc,
            upc_mux=self.upc_mux,
            status=self.reg_file.status,
            sp=self.reg_file.sp,
            osp=self.reg_file.osp,
            instr_reg=self.reg_file.instr,
            imm_reg=self.reg_file.imm,
            memory=self.memory,
            writeback_mux=self.writeback_mux,
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
        }
        if dst in reg_map:
            reg_map[dst].write(res)
        elif dst == Reg.EA.value:
            self.reg_file.ea.write(res[:2])
        elif dst == Reg.EB.value:
            self.reg_file.eb.write(res[:2])
        elif dst == Reg.C:
            self.reg_file.c.write(res[:1])
        elif dst in (Reg.NONE, Reg.STATUS, Reg.UPC):
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


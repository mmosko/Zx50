"""Top-level FPGA system model."""
from fpu_emu.blocks.adder_block import AdderBlock
from fpu_emu.blocks.functional_block import BlockInputs
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.registers import Registers
from fpu_emu.hardware.rom import Rom


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

        # | `0b0000`   | AL                | Yes (`0b000`)           | Yes (`0b0000`)      | AL (or AX if W=1)           |
        # | `0b0001`   | AH                | Yes (`0b001`)           | Yes (`0b0001`)      | AH                          |
        # | `0b0010`   | EA                | Yes (`0b010`)           | Yes (`0b0010`)      | EA (12-bit)                 |
        # | `0b0011`   | EB                | Yes (`0b011`)           | Yes (`0b0011`)      | EB (12-bit)                 |
        # | `0b0100`   | IMM               | Yes (`0b100`)           | Yes (`0b0100`)      | — (No write / CMP)          |
        # | `0b0101`   | C                 | Yes (`0b101`)           | Yes (`0b0101`)      | C (8-bit)                   |
        # | `0b0110`   | BL                | —                       | Yes (`0b0110`)      | BL (or BX if W=1)           |
        # | `0b0111`   | BH                | —                       | Yes (`0b0111`)      | BH                          |
        # | `0b1000`   | DL                | —                       | Yes (`0b1000`)      | DL (or DX if W=1)           |
        # | `0b1001`   | DH                | —                       | Yes (`0b1001`)      | DH                          |
        # | `0b1010`   | FL                | —                       | Yes (`0b1010`)      | FL (or FX if W=1)           |
        # | `0b1011`   | FH                | —                       | Yes (`0b1011`)      | FH                          |
        # | `0b1100`   | TOS               | —                       | —                   | Hardware Stack Push         |
        # | `0b1101`   | UPC               | —                       | —                   | UPC (Branch/Return)         |
        # | `0b1110`   | HOST_OUT          | —                       | —                   | Port 0x70 Staging Reg       |
        # | `0b1111`   | NONE              | —                       | —                   | Discard result (CMP, TEST)  |

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
            clock=self.clock
        )

        self.blocks = [
            self.adder,     # 0
            self.adder,     # 1
            None,           # 2
            None,           # 3
            None            # 4
        ]

        self.dispatcher = Dispatcher()
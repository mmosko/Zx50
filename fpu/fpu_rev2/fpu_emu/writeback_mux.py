from typing import List

from fpu_emu.blocks.functional_block import FunctionalBlock
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg


class WritebackMux:
    def __init__(self, blocks: List[FunctionalBlock]):
        # 32-bit result mux
        self.res_mux = Mux(name="res", inputs=[
            b.outputs.block_res for b in blocks
        ])

        # 4-bit write back register select
        self.res_sel_mux = Mux(name="res_sel", inputs=[
            b.outputs.block_res_sel for b in blocks
        ])

        # status register byte
        self.status_mux = Mux(name="status", inputs=[
            b.outputs.res_status for b in blocks
        ])

        # status register bit select mask
        self.status_wr_sel_mux = Mux(name="status_wr_sel", inputs=[
            b.outputs.status_wr_sel for b in blocks
        ])

        # exec_wb select
        self.exec_wb_mux = Mux(name="exec_wb", inputs=[
            b.outputs.exec_wb for b in blocks
        ])

        self.exec_done_mux = Mux(name="exec_done", inputs=[
            b.outputs.exec_done for b in blocks
        ])

        # Default reset state selects block 0
        self.set_block(0)

    def set_block(self, block_num: int):
        self.res_mux.select(block_num)
        self.res_sel_mux.select(block_num)
        self.status_mux.select(block_num)
        self.status_wr_sel_mux.select(block_num)
        self.exec_wb_mux.select(block_num)
        self.exec_done_mux.select(block_num)

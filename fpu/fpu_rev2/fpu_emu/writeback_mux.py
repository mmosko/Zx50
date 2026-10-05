from typing import List

from fpu_emu.blocks.functional_block import FunctionalBlock
from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.reg import Reg


class WritebackMux:
    """
    The Control block should not be routed through this MUX. It has dedicated output functionality.
    SELECT indices are the same, but control inputs are wired to dummies that would be absent in hardware.
    """
    def __init__(self, blocks: List[FunctionalBlock]):
        # Dummy buses for block 3 (Control) which has dedicated wiring instead of writeback
        self._dummy_res = Bus(name="dummy_res", size_in_bits=32)
        self._dummy_res.set(0)
        self._dummy_res_sel = Bus(name="dummy_res_sel", size_in_bits=4)
        self._dummy_res_sel.set(Reg.NONE.value)
        self._dummy_status = Bus(name="dummy_status", size_in_bits=8)
        self._dummy_status.set(0)
        self._dummy_status_wr_sel = Bus(name="dummy_status_wr_sel", size_in_bits=8)
        self._dummy_status_wr_sel.set(0)
        self._dummy_exec_wb = Bus(name="dummy_exec_wb", size_in_bits=1)
        self._dummy_exec_wb.set(0)
        self._dummy_exec_done = Bus(name="dummy_exec_done", size_in_bits=1)
        self._dummy_exec_done.set(0)

        # 32-bit result mux
        self.res_mux = Mux(name="res", inputs=[
            self._dummy_res if i == 3 else b.outputs.block_res
            for i, b in enumerate(blocks)
        ])

        # 4-bit write back register select
        self.res_sel_mux = Mux(name="res_sel", inputs=[
            self._dummy_res_sel if i == 3 else b.outputs.block_res_sel
            for i, b in enumerate(blocks)
        ])

        # status register byte
        self.status_mux = Mux(name="status", inputs=[
            self._dummy_status if i == 3 else b.outputs.res_status
            for i, b in enumerate(blocks)
        ])

        # status register bit select mask
        self.status_wr_sel_mux = Mux(name="status_wr_sel", inputs=[
            self._dummy_status_wr_sel if i == 3 else b.outputs.status_wr_sel
            for i, b in enumerate(blocks)
        ])

        # exec_wb select
        self.exec_wb_mux = Mux(name="exec_wb", inputs=[
            self._dummy_exec_wb if i == 3 else b.outputs.exec_wb
            for i, b in enumerate(blocks)
        ])

        self.exec_done_mux = Mux(name="exec_done", inputs=[
            self._dummy_exec_done if i == 3 else b.outputs.exec_done
            for i, b in enumerate(blocks)
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

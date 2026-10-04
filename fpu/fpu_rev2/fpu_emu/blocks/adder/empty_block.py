from typing import Callable

from fpu_emu.blocks.functional_block import FunctionalBlock, BlockInputs
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory


class EmptyBlock(FunctionalBlock):
    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, writeback: Callable, clock: Clock, **kwargs):
        super().__init__(name, inputs, memory, writeback, clock)

    def execute(self):
        self._clock.tick()
        # would set the EXEC_DONE flag, but that is implicit in returning
        self._outputs.exec_done.set(b'0x01')

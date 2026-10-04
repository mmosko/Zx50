from dataclasses import dataclass

from fpu_emu.hardware.bus import Bus
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.memory import Memory
from fpu_emu.hardware.mux import Mux
from fpu_emu.hardware.register import Register


@dataclass
class BlockInputs:
    ha_mux: Mux
    hb_mux: Mux
    status: Register
    instr: Register
    exec_ready: Register


@dataclass
class BlockOutputs:
    block_res: Bus
    block_res_sel: Bus
    res_status: Bus
    status_wr_sel: Bus
    exec_wb: Bus
    exec_done: Bus


class FunctionalBlock:
    """
    A Functional block is a set of logic that is behind one AND wall to regulate power consumption.
    """

    def __init__(self, name: str, inputs: BlockInputs, memory: Memory, clock: Clock) -> None:
        self._name = name
        self._inputs = inputs
        self._memory = memory
        self._clock = clock

        self._outputs = BlockOutputs(
            block_res=Bus(name=f"{name}_res", size_in_bits=32),
            block_res_sel=Bus(name=f"{name}_res_sel", size_in_bits=4),
            res_status=Bus(name=f"{name}_res_status", size_in_bits=8),
            status_wr_sel=Bus(name=f"{name}_wr_sel", size_in_bits=8),
            exec_wb=Bus(name=f"{name}_exec_wb", size_in_bits=1),
            exec_done=Bus(name=f"{name}_exec_done", size_in_bits=1),
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def outputs(self) -> BlockOutputs:
        return self._outputs

    def execute(self):
        pass

from typing import List, Optional

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.ebr import EBR, NullEbr


@fpga_resource(
    approach="SysMEM EBR Blocks (EBR 0/1/2/3 1024x32 DATA RAM)",
    luts=0,
    ffs=0,
    ebr=4,
    delay_ns=3.2,
    cycles=1,
    shared_unit="ebr_sysmem_ram",
)
class Memory:
    def __init__(self, rom_blocks: List[Optional[List[int]]], clock: Clock) -> None:
        self._ebr = [
            EBR(name="0", size=1024, width=32, read_only_buffer=rom_blocks[0], clock=clock, readonly=False),
            NullEbr(clock),
            NullEbr(clock),
            NullEbr(clock),
            EBR(name="4", size=1024, width=32, read_only_buffer=rom_blocks[1], clock=clock, readonly=True),
            NullEbr(clock),
            NullEbr(clock),
            NullEbr(clock)
        ]

    def read(self, block: int, addr: int) -> int:
        return self._ebr[block].read(addr)

    def write(self, block: int, addr: int, data: int) -> None:
        self._ebr[block].write(addr, data)

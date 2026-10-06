from typing import List, Optional

from fpu_emu.fpga_resource import fpga_resource
from fpu_emu.hardware.clock import Clock
from fpu_emu.hardware.ebr import EBR


@fpga_resource(
    approach="SysMEM EBR Blocks (EBR 0/1 Stack/Scratch RAM, EBR 2/3 Constants ROM, EBR 4 Seed LUT ROM)",
    luts=0,
    ffs=0,
    ebr=5,
    delay_ns=3.2,
    cycles=1,
    shared_unit="ebr_sysmem_ram",
)
class Memory:
    def __init__(self, rom_blocks: List[Optional[List[int]]], clock: Clock) -> None:
        self._ebr = [
            EBR(name="0", size=512, width=18, read_only_buffer=rom_blocks[0], clock=clock),
            EBR(name="1", size=512, width=18, read_only_buffer=rom_blocks[1], clock=clock),
            EBR(name="2", size=512, width=18, read_only_buffer=rom_blocks[2], clock=clock),
            EBR(name="3", size=512, width=18, read_only_buffer=rom_blocks[3], clock=clock),
            EBR(name="4", size=512, width=18, read_only_buffer=rom_blocks[4], clock=clock),
            EBR(name="5", size=512, width=18, read_only_buffer=rom_blocks[5], clock=clock),
            EBR(name="6", size=512, width=18, read_only_buffer=rom_blocks[6], clock=clock),
            EBR(name="7", size=512, width=18, read_only_buffer=rom_blocks[7], clock=clock),
        ]

    def read(self, block: int, addr: int) -> int:
        return self._ebr[block].read(addr)

    def write(self, block: int, addr: int, data: int) -> None:
        self._ebr[block].write(addr, data)

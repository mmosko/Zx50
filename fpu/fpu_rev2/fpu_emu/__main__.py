"""CLI entry point for the Zx50 FPU Rev2 emulator.

Prints the MachXO2 FPGA resource utilization report and microcode capacity.
"""

from fpu_emu.fpga_resource import FpgaResourceRegistry
from fpu_emu.micro_code import MicroCode

# Ensure all annotated hardware modules are imported and registered
import fpu_emu.blocks.adder.adder_block  # noqa: F401
import fpu_emu.blocks.adder.adder_core  # noqa: F401
import fpu_emu.blocks.adder.booth_mul  # noqa: F401
import fpu_emu.blocks.adder.div_core  # noqa: F401
import fpu_emu.blocks.control.control_block  # noqa: F401
import fpu_emu.blocks.control.count_adder  # noqa: F401
import fpu_emu.blocks.logic_block  # noqa: F401
import fpu_emu.blocks.memory.memory_block  # noqa: F401
import fpu_emu.blocks.memory.stack_adder  # noqa: F401
import fpu_emu.blocks.shifter.priority_encoder  # noqa: F401
import fpu_emu.blocks.shifter.shifter_adder  # noqa: F401
import fpu_emu.blocks.shifter.shifter_block  # noqa: F401
import fpu_emu.dispatcher  # noqa: F401
import fpu_emu.fpga_model  # noqa: F401
import fpu_emu.hardware.memory  # noqa: F401
import fpu_emu.hardware.registers  # noqa: F401
import fpu_emu.hardware.upc_adder  # noqa: F401
import fpu_emu.micro_code  # noqa: F401
import fpu_emu.writeback_mux  # noqa: F401


def generate_microcode_report() -> str:
    """Generates the microcode capacity and utilization summary."""
    total = MicroCode.total_instructions()
    max_cap = MicroCode.MAX_MICRO_INSTRUCTIONS
    remaining = MicroCode.remaining_capacity()
    pct = (total / max_cap) * 100
    return (
        "**Microcode ROM Capacity (EBR 5 & 6, 512x32):**\n"
        f"- **Utilized Instructions:** {total} / {max_cap} ({pct:.1f}%)\n"
        f"- **Remaining Capacity:** {remaining} instructions"
    )


def print_resource_report() -> None:
    """Prints the MachXO2-2000 FPGA resource utilization report."""
    print(FpgaResourceRegistry.generate_report())


def print_microcode_report() -> None:
    """Prints the microcode capacity and utilization summary."""
    print(generate_microcode_report())


def main() -> None:
    """Main CLI entry point."""
    print_resource_report()
    print()
    print_microcode_report()


if __name__ == "__main__":  # pragma: no cover
    main()

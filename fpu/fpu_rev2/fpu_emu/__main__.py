"""CLI entry point for the Zx50 FPU Rev2 emulator.

Prints the MachXO2 FPGA resource utilization report from FpgaResourceRegistry.
"""

from fpu_emu.fpga_resource import FpgaResourceRegistry

# Ensure all annotated hardware modules are imported and registered
import fpu_emu.blocks.adder.adder_block  # noqa: F401
import fpu_emu.blocks.adder.adder_core  # noqa: F401
import fpu_emu.blocks.adder.booth_mul  # noqa: F401
import fpu_emu.dispatcher  # noqa: F401
import fpu_emu.hardware.memory  # noqa: F401
import fpu_emu.hardware.registers  # noqa: F401
import fpu_emu.hardware.rom  # noqa: F401
import fpu_emu.micro_code  # noqa: F401


def print_resource_report() -> None:
    """Prints the MachXO2-2000 FPGA resource utilization report."""
    print(FpgaResourceRegistry.generate_report())


def main() -> None:
    """Main CLI entry point."""
    print_resource_report()


if __name__ == "__main__":  # pragma: no cover
    main()

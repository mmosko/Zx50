"""Automated unit test verifying FPGA hardware resource budget and MachXO2-2000 constraints."""

import unittest
from fpu_emu.fpga_resource import FpgaResourceRegistry

# Import all annotated modules to populate registry
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


class TestFpgaBudget(unittest.TestCase):
    """Verifies that all annotated FPGA primitives comply with physical MachXO2 limits."""

    def test_machxo2_budget_constraints(self):
        """Checks for zero constraint violations across all registered units."""
        violations = FpgaResourceRegistry.check_constraints()
        self.assertEqual(
            violations,
            [],
            f"FPGA resource constraints violated: {violations}",
        )

    def test_total_utilization(self):
        """Verifies exact totals against budget headroom."""
        totals = FpgaResourceRegistry.get_totals()

        # MachXO2-2000HC absolute limits:
        # LUT4: 2112, Slices: 1056, FF: 2112, EBR: 8, DSP: 0
        self.assertLessEqual(totals["luts"], 2112)
        self.assertLessEqual(totals["slices_ccu2c"], 1056)
        self.assertLessEqual(totals["ffs"], 2112)
        self.assertLessEqual(totals["ebr_blocks"], 8)
        self.assertEqual(totals["dsp_mults"], 0)

        # Datapath baseline must stay well under 50% of device LUTs
        self.assertLess(
            totals["luts"],
            1056,
            f"Baseline LUT4 utilization ({totals['luts']}) exceeds 50% device budget (1056 LUTs)",
        )

    def test_microcode_instruction_budget(self):
        """Verifies total microcode instructions do not exceed the 512 EBR ROM limit."""
        from fpu_emu.micro_code import MicroCode

        total = MicroCode.total_instructions()
        remaining = MicroCode.remaining_capacity()

        self.assertLessEqual(
            total,
            MicroCode.MAX_MICRO_INSTRUCTIONS,
            f"Total microcode instructions ({total}) exceeds EBR 512-word capacity limit",
        )
        self.assertEqual(remaining, MicroCode.MAX_MICRO_INSTRUCTIONS - total)
        self.assertGreaterEqual(remaining, 0)

    def test_budget_report_generation(self):
        """Verifies report markdown format."""
        report = FpgaResourceRegistry.generate_report()
        self.assertIn("# MachXO2-2000 FPGA Resource Utilization Report", report)
        self.assertIn("register_file", report)
        self.assertIn("alu_adder32", report)
        self.assertIn("alu_booth_mul", report)
        self.assertIn("alu_div_core", report)
        self.assertIn("adder_block", report)
        self.assertIn("control_block", report)
        self.assertIn("count_adder", report)
        self.assertIn("logic_block", report)
        self.assertIn("memory_block", report)
        self.assertIn("stack_adder", report)
        self.assertIn("upc_adder", report)
        self.assertIn("writeback_mux", report)
        self.assertIn("datapath_muxes", report)
        self.assertIn("fpga_model_overhead", report)
        self.assertIn("priority_encoder32", report)
        self.assertIn("shifter_adder", report)
        self.assertIn("shifter_block", report)
        self.assertIn("dispatcher_sequencer", report)
        self.assertIn("ebr_microcode_rom", report)
        self.assertIn("ebr_sysmem_ram", report)

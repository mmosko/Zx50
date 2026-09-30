"""Automated unit test verifying FPGA hardware resource budget and MachXO2-2000 constraints."""

import unittest
from fpu_emu.fpga_resource import FpgaResourceRegistry

# Import all annotated hardware datapath modules to populate registry
import fpu_emu.alu.adder  # noqa: F401
import fpu_emu.alu.logic  # noqa: F401
import fpu_emu.alu.shifter  # noqa: F401
import fpu_emu.alu.booth_mul  # noqa: F401
import fpu_emu.alu.lzc  # noqa: F401
import fpu_emu.alu.ieee754_exp  # noqa: F401
import fpu_emu.memory.registers  # noqa: F401


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

        # Datapath core units must stay well under 50% of the chip to leave room for sequencer/microcode
        self.assertLess(
            totals["luts"],
            1000,
            f"ALU & Bus LUT4 utilization ({totals['luts']}) exceeds 1000 LUT budget",
        )

    def test_budget_report_generation(self):
        """Verifies report markdown format."""
        report = FpgaResourceRegistry.generate_report()
        self.assertIn("# MachXO2-2000 FPGA Resource Utilization Report", report)
        self.assertIn("alu_adder32", report)
        self.assertIn("alu_shifter32", report)
        self.assertIn("alu_logic32", report)
        self.assertIn("alu_booth_mul", report)
        self.assertIn("alu_lzc32", report)
        self.assertIn("alu_exp12", report)
        self.assertIn("bus_ha_mux", report)
        self.assertIn("bus_hb_mux", report)
        self.assertIn("bus_res_mux", report)
        self.assertIn("Total Dedicated / Shared Hardware", report)

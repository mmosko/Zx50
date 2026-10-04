"""Unit tests for __main__.py CLI entry point."""

from unittest.mock import patch
from io import StringIO
import fpu_emu.__main__ as main_module


def test_main_prints_report():
    """Verifies that main() prints the FPGA resource report."""
    output = StringIO()
    with patch("sys.stdout", output):
        main_module.main()

    rendered = output.getvalue()
    assert "# MachXO2-2000 FPGA Resource Utilization Report" in rendered
    assert "alu_adder32" in rendered
    assert "alu_booth_mul" in rendered
    assert "register_file" in rendered
    assert "ebr_sysmem" in rendered
    assert "micro_sequencer" in rendered
    assert "Total Dedicated / Shared Hardware" in rendered

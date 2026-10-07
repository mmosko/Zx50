"""Unit tests for __main__.py CLI reporting."""

import io
from unittest.mock import patch
from fpu_emu.__main__ import generate_microcode_report, main, print_microcode_report, print_resource_report


from fpu_emu.micro_code import MicroCode


def test_generate_microcode_report() -> None:
    report = generate_microcode_report()
    assert f"**Microcode ROM Capacity (EBR 5 & 6, {MicroCode.MAX_MICRO_INSTRUCTIONS}x32):**" in report
    assert "Utilized Instructions:" in report
    assert "Remaining Capacity:" in report
    assert f"/ {MicroCode.MAX_MICRO_INSTRUCTIONS}" in report


def test_main_cli_execution() -> None:
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        main()
        output = fake_out.getvalue()
        assert "# MachXO2-2000 FPGA Resource Utilization Report" in output
        assert "**Microcode ROM Capacity" in output
        assert str(MicroCode.MAX_MICRO_INSTRUCTIONS) in output


def test_print_functions() -> None:
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        print_resource_report()
        assert "MachXO2-2000 FPGA Resource Utilization Report" in fake_out.getvalue()

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        print_microcode_report()
        assert "Microcode ROM Capacity" in fake_out.getvalue()

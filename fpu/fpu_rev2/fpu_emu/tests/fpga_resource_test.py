"""Unit tests for FPGA resource accounting, decorators, and constraint validation."""

from fpu_emu.fpga_resource import (
    FpgaResourceRegistry,
    fpga_resource,
)


def setup_function():
    """Clear registry before each test."""
    FpgaResourceRegistry.clear()


def test_fpga_resource_decorator():
    @fpga_resource(
        approach="32 XOR gates + CCU2C fast carry-chain",
        luts=23,
        slices_ccu2c=16,
        ffs=4,
        delay_ns=3.9,
        cycles=1,
        shared_unit="alu_adder32",
    )
    def dummy_adder():
        pass

    assert hasattr(dummy_adder, "__fpga_resource__")
    res = dummy_adder.__fpga_resource__  # pyright: ignore[reportFunctionMemberAccess]
    assert res.luts == 23
    assert res.slices_ccu2c == 16
    assert res.ffs == 4
    assert res.delay_ns == 3.9
    assert res.shared_unit == "alu_adder32"

    # Verify registration
    entries = FpgaResourceRegistry.all_entries()
    assert "test_fpga_resource_decorator.<locals>.dummy_adder" in entries


def test_unique_hardware_units_deduplication():
    @fpga_resource(
        approach="Shared adder",
        luts=23,
        slices_ccu2c=16,
        shared_unit="alu_adder32",
    )
    def add_func():
        pass

    @fpga_resource(
        approach="Shared adder (sub mode)",
        luts=23,
        slices_ccu2c=16,
        shared_unit="alu_adder32",
    )
    def sub_func():
        pass

    unique = FpgaResourceRegistry.unique_hardware_units()
    assert len(unique) == 1
    assert "alu_adder32" in unique
    assert FpgaResourceRegistry.total_luts() == 23


def test_constraint_checking_passes():
    @fpga_resource(approach="Core", luts=500, ffs=400, ebr=2)
    def core():
        pass

    violations = FpgaResourceRegistry.check_constraints()
    assert len(violations) == 0


def test_constraint_checking_violations():
    @fpga_resource(approach="Gigantic core", luts=3000, ffs=2500, ebr=10, dsp=2)
    def huge():
        pass

    violations = FpgaResourceRegistry.check_constraints()
    assert len(violations) == 4
    assert any("LUT limit exceeded" in v for v in violations)
    assert any("FF limit exceeded" in v for v in violations)
    assert any("EBR block limit exceeded" in v for v in violations)
    assert any("DSP limit exceeded" in v for v in violations)


def test_generate_report():
    @fpga_resource(
        approach="Logarithmic barrel shifter",
        luts=104,
        delay_ns=4.1,
        cycles=1,
        shared_unit="alu_shifter32",
    )
    def shifter():
        pass

    report = FpgaResourceRegistry.generate_report()
    assert "# MachXO2-2000 FPGA Resource Utilization Report" in report
    assert "alu_shifter32" in report
    assert "104" in report

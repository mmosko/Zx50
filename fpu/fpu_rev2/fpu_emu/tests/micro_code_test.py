"""Unit tests for MicroCode lookup table and EBR instruction budget tracking."""

import pytest
from fpu_emu.micro_code import MicroCode
from fpu_emu.user_opcodes import UserOpcode


def test_microcode_instruction_budget_under_512() -> None:
    """Tests that the total microcode size complies with the 512-word EBR capacity."""
    total = MicroCode.total_instructions()
    assert total > 0, "MicroCode table must not be empty"
    assert total <= MicroCode.MAX_MICRO_INSTRUCTIONS, (
        f"MicroCode size ({total}) exceeds 512 EBR word limit"
    )


def test_microcode_remaining_capacity() -> None:
    """Tests remaining capacity calculation."""
    total = MicroCode.total_instructions()
    remaining = MicroCode.remaining_capacity()
    assert remaining == MicroCode.MAX_MICRO_INSTRUCTIONS - total
    assert remaining >= 0


def test_microcode_validate_budget_raises_on_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests that validate_budget raises ValueError when total exceeds limit."""
    # Temporarily lower the maximum limit to simulate overflow
    monkeypatch.setattr(MicroCode, "MAX_MICRO_INSTRUCTIONS", 10)
    with pytest.raises(ValueError, match="exceeds EBR capacity limit"):
        MicroCode.validate_budget()

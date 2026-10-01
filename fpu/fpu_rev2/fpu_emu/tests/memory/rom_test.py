"""Unit tests for Rom model and image consistency with tools/build_flash.py."""

import hashlib
import os
import pytest
from fpu_emu.memory.rom import (
    Rom,
    ROM_SIZE,
)


def test_rom_default_load():
    """Verify that Rom loads the packaged fpu_flash.bin correctly."""
    rom = Rom()
    assert rom.size == ROM_SIZE == 32768


def test_rom_load_bounds():
    """Verify bounds checking on load_byte, load_u16, and load."""
    rom = Rom()

    # Valid reads
    b0 = rom.load_byte(0)
    assert 0 <= b0 <= 255
    u0 = rom.load_u16(0)
    assert 0 <= u0 <= 65535
    data = rom.load(0, 4)
    assert len(data) == 4

    # Out of bounds
    with pytest.raises(IndexError):
        rom.load_byte(-1)
    with pytest.raises(IndexError):
        rom.load_byte(ROM_SIZE)

    with pytest.raises(IndexError):
        rom.load_u16(ROM_SIZE - 1)  # needs 2 bytes

    with pytest.raises(IndexError):
        rom.load(ROM_SIZE - 2, 4)

    with pytest.raises(ValueError):
        rom.load(0, 0)


def test_rom_sqrt_seed_table():
    """Verify the reciprocal square root seeds in the ROM."""
    rom = Rom()

    # Index 0: Even exponent, fraction near 0 -> M approx 1.0 -> 1/sqrt(M) approx 1.0 (Q0.16 approx 0xFF..)
    seed_0 = rom.load_sqrt_seed(0)
    # 1.0 / sqrt(1.0039) * 65536 approx 65406 (0xFFA6)
    assert 0xF000 <= seed_0 <= 0xFFFF

    # Index 127: Even exponent, fraction near 1.0 -> M approx 2.0 -> 1/sqrt(2) approx 0.7071 -> 46341 (0xB505)
    seed_127 = rom.load_sqrt_seed(127)
    assert 45000 <= seed_127 <= 47000

    # Index 128: Odd exponent, fraction near 0 -> M approx 2.0 -> 1/sqrt(2) approx 0.7071 -> 46341
    seed_128 = rom.load_sqrt_seed(128)
    assert 45000 <= seed_128 <= 47000

    # Index 255: Odd exponent, fraction near 1.0 -> M approx 4.0 -> 1/sqrt(4) = 0.5 -> 32768 (0x8000)
    seed_255 = rom.load_sqrt_seed(255)
    assert 32000 <= seed_255 <= 33000


def test_rom_image_consistency_with_build_flash():
    """Drift-prevention test: verify that fpu_flash.bin matches tools/build_flash.py."""
    import sys

    # Add tools directory to sys.path for this verification test only
    tools_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools"))
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    try:
        from build_flash import generate_flash_image
    finally:
        if tools_dir in sys.path:
            sys.path.remove(tools_dir)

    expected_image = generate_flash_image()
    rom = Rom()

    expected_sha = hashlib.sha256(expected_image).hexdigest()
    actual_sha = hashlib.sha256(rom._data).hexdigest()

    assert actual_sha == expected_sha, (
        f"Drift detected: fpu_flash.bin SHA256 ({actual_sha}) does not match "
        f"tools/build_flash.py generated image SHA256 ({expected_sha}). "
        f"Please run 'python3 tools/build_flash.py' to update the ROM artifacts."
    )


def test_rom_constants_and_errors(tmp_path):
    rom = Rom()

    # load_const32 and load_const64
    c32 = rom.load_const32(0xA0)  # PI single
    assert len(c32) == 4
    c64 = rom.load_const64(0xA0)  # PI double
    assert len(c64) == 8

    # Index errors
    with pytest.raises(IndexError):
        rom.load_sqrt_seed(256)
    with pytest.raises(IndexError):
        rom.load_const32(0x9F)
    with pytest.raises(IndexError):
        rom.load_const64(0xB0)

    # Non-existent ROM fallback
    fake_rom_path = str(tmp_path / "nonexistent.bin")
    fallback_rom = Rom(rom_path=fake_rom_path)
    assert fallback_rom.size == ROM_SIZE
    assert fallback_rom.load_byte(0) == 0xFF

    # Invalid ROM size file
    bad_rom_file = tmp_path / "bad_size.bin"
    bad_rom_file.write_bytes(b"too short")
    with pytest.raises(ValueError, match="Invalid ROM image size"):
        Rom(rom_path=str(bad_rom_file))


def test_rom_cordic_atan_tables():
    """Verify CORDIC arctangent tables in ROM for 32-bit (Q2.30) and 64-bit (Q2.62)."""
    rom = Rom()

    # 32-bit Q2.30 tests
    assert rom.load_cordic_atan32(0) == 0x3243F6A9  # pi/4
    assert rom.load_cordic_atan32(1) == 0x1DAC6705  # atan(0.5)
    assert rom.load_cordic_atan32(2) == 0x0FADBAFD  # atan(0.25)
    assert rom.load_cordic_atan32(31) >= 0

    with pytest.raises(IndexError):
        rom.load_cordic_atan32(-1)
    with pytest.raises(IndexError):
        rom.load_cordic_atan32(32)

    # 64-bit Q2.62 tests
    assert rom.load_cordic_atan64(0) == 0x3243F6A8885A308D  # pi/4
    assert rom.load_cordic_atan64(1) == 0x1DAC670561BB4F69  # atan(0.5)
    assert rom.load_cordic_atan64(2) == 0x0FADBAFC96406EB1  # atan(0.25)
    assert rom.load_cordic_atan64(63) >= 0

    with pytest.raises(IndexError):
        rom.load_cordic_atan64(-1)
    with pytest.raises(IndexError):
        rom.load_cordic_atan64(64)


def test_rom_trig_constants():
    """Verify trigonometric and CORDIC constants table."""
    from fpu_emu.memory.rom import TrigConstSlot

    rom = Rom()

    # Fixed-point CORDIC scale factors and range reduction
    assert rom.load_trig_const32(TrigConstSlot.INV_K_32) == 0x26DD3B6A
    assert rom.load_trig_const64(TrigConstSlot.INV_K_64) == 0x26DD3B6A10D7969A

    assert rom.load_trig_const32(TrigConstSlot.HALF_PI_32) == 0x6487ED51
    assert rom.load_trig_const64(TrigConstSlot.HALF_PI_64) == 0x6487ED5110B4611A

    assert rom.load_trig_const32(TrigConstSlot.TWO_OVER_PI_32) == 0x517CC1B7
    assert rom.load_trig_const64(TrigConstSlot.TWO_OVER_PI_64) == 0x517CC1B727220A95

    assert rom.load_trig_const32(TrigConstSlot.QUARTER_PI_32) == 0x3243F6A9
    assert rom.load_trig_const64(TrigConstSlot.QUARTER_PI_64) == 0x3243F6A8885A308D

    # IEEE-754 representations
    assert rom.load_trig_const32(TrigConstSlot.TWO_OVER_PI_F32) == 0x3F22F983
    assert rom.load_trig_const64(TrigConstSlot.TWO_OVER_PI_F64) == 0x3FE45F306DC9C883
    assert rom.load_trig_const32(TrigConstSlot.HALF_PI_F32) == 0x3FC90FDB
    assert rom.load_trig_const64(TrigConstSlot.HALF_PI_F64) == 0x3FF921FB54442D18
    assert rom.load_trig_const32(TrigConstSlot.PI_F32) == 0x40490FDB
    assert rom.load_trig_const64(TrigConstSlot.PI_F64) == 0x400921FB54442D18
    assert rom.load_trig_const32(TrigConstSlot.INV_K_F32) == 0x3F1B74EE
    assert rom.load_trig_const64(TrigConstSlot.INV_K_F64) == 0x3FE36E9DE57788A5

    # Bounds check
    with pytest.raises(IndexError):
        rom.load_trig_const32(-1)
    with pytest.raises(IndexError):
        rom.load_trig_const32(16)
    with pytest.raises(IndexError):
        rom.load_trig_const64(-1)
    with pytest.raises(IndexError):
        rom.load_trig_const64(16)

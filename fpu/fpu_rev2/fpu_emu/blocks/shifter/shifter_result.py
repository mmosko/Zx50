from dataclasses import dataclass


@dataclass(frozen=True)
class ShifterResult:
    """Result of a shifter block operation."""

    res: int  # 32-bit integer result
    cf: bool = False
    zf: bool = False
    sf: bool = False
    vf: bool = False

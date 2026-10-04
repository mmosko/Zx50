"""FPGA resource accounting and validation framework for Zx50 FPU.

Tracks hardware utilization (LUT4s, PFU slices, Flip-Flops, EBR blocks, DSP multipliers,
delays, and cycles) against the target Lattice MachXO2-2000 (LCMXO2-2000HC) device constraints.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


# Target Device Hardware Constraints (MachXO2 LCMXO2-2000HC)
MACHXO2_2000_MAX_LUTS = 2112
MACHXO2_2000_MAX_SLICES = 1056
MACHXO2_2000_MAX_FFS = 2112
MACHXO2_2000_MAX_EBR_BLOCKS = 8
MACHXO2_2000_MAX_DSP = 0


@dataclass(frozen=True)
class FpgaResource:
    """Hardware resource specification for a module or primitive."""

    approach: str
    luts: int
    slices_ccu2c: int = 0
    ffs: int = 0
    ebr: int = 0
    dsp: int = 0
    delay_ns: float = 0.0
    cycles: int = 1
    shared_unit: Optional[str] = None  # Grouping key for shared hardware units


class FpgaResourceRegistry:
    """Global registry aggregating all annotated FPGA resources."""

    _entries: Dict[str, FpgaResource] = {}

    @classmethod
    def register(cls, identifier: str, resource: FpgaResource) -> None:
        """Registers a named resource specification."""
        cls._entries[identifier] = resource

    @classmethod
    def clear(cls) -> None:
        """Clears the registry (useful for testing)."""
        cls._entries.clear()

    @classmethod
    def all_entries(cls) -> Dict[str, FpgaResource]:
        """Returns all registered resource specifications."""
        return dict(cls._entries)

    @classmethod
    def unique_hardware_units(cls) -> Dict[str, FpgaResource]:
        """Returns hardware specifications de-duplicated by shared_unit."""
        units: Dict[str, FpgaResource] = {}
        for name, res in cls._entries.items():
            key = res.shared_unit if res.shared_unit is not None else name
            if key not in units:
                units[key] = res
        return units

    @classmethod
    def total_luts(cls) -> int:
        """Calculates total unique LUT4 utilization."""
        return sum(res.luts for res in cls.unique_hardware_units().values())

    @classmethod
    def total_ccu2c_slices(cls) -> int:
        """Calculates total unique CCU2C carry slices."""
        return sum(res.slices_ccu2c for res in cls.unique_hardware_units().values())

    @classmethod
    def total_ffs(cls) -> int:
        """Calculates total unique flip-flops."""
        return sum(res.ffs for res in cls.unique_hardware_units().values())

    @classmethod
    def total_ebr_blocks(cls) -> int:
        """Calculates total unique EBR blocks."""
        return sum(res.ebr for res in cls.unique_hardware_units().values())

    @classmethod
    def total_dsp(cls) -> int:
        """Calculates total unique DSP blocks."""
        return sum(res.dsp for res in cls.unique_hardware_units().values())

    @classmethod
    def get_totals(cls) -> Dict[str, int]:
        """Returns total resource usage across all unique shared units."""
        return {
            "luts": cls.total_luts(),
            "slices_ccu2c": cls.total_ccu2c_slices(),
            "ffs": cls.total_ffs(),
            "ebr_blocks": cls.total_ebr_blocks(),
            "dsp_mults": cls.total_dsp(),
        }

    @classmethod
    def check_constraints(cls) -> List[str]:
        """Validates current totals against MachXO2-2000 constraints.

        Returns a list of violation messages (empty if all pass).
        """
        violations = []
        if cls.total_luts() > MACHXO2_2000_MAX_LUTS:
            violations.append(f"LUT limit exceeded: {cls.total_luts()} > {MACHXO2_2000_MAX_LUTS}")
        if cls.total_ffs() > MACHXO2_2000_MAX_FFS:
            violations.append(f"FF limit exceeded: {cls.total_ffs()} > {MACHXO2_2000_MAX_FFS}")
        if cls.total_ebr_blocks() > MACHXO2_2000_MAX_EBR_BLOCKS:
            violations.append(f"EBR block limit exceeded: {cls.total_ebr_blocks()} > {MACHXO2_2000_MAX_EBR_BLOCKS}")
        if cls.total_dsp() > MACHXO2_2000_MAX_DSP:
            violations.append(f"DSP limit exceeded: MachXO2 has no DSP blocks, used {cls.total_dsp()}")
        return violations

    @classmethod
    def generate_report(cls) -> str:
        """Generates a formatted markdown summary table of FPGA utilization."""
        lines = [
            "# MachXO2-2000 FPGA Resource Utilization Report",
            "",
            "| Module / Unit | Approach | LUT4s | CCU2C Slices | FFs | EBR | Delay (ns) | Cycles |",
            "|---|---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
        units = cls.unique_hardware_units()
        for name, res in sorted(units.items()):
            lines.append(
                f"| `{name}` | {res.approach} | {res.luts} | {res.slices_ccu2c} | {res.ffs} | {res.ebr} | {res.delay_ns:.1f} | {res.cycles} |"
            )

        tot_luts = cls.total_luts()
        tot_slices = cls.total_ccu2c_slices()
        tot_ffs = cls.total_ffs()
        tot_ebr = cls.total_ebr_blocks()

        lines.extend(
            [
                "",
                "**Total Dedicated / Shared Hardware:**",
                f"- **LUT4s:** {tot_luts} / {MACHXO2_2000_MAX_LUTS} ({tot_luts / MACHXO2_2000_MAX_LUTS * 100:.1f}%)",
                f"- **Carry Slices (CCU2C):** {tot_slices} / {MACHXO2_2000_MAX_SLICES} ({tot_slices / MACHXO2_2000_MAX_SLICES * 100:.1f}%)",
                f"- **Flip-Flops (FF):** {tot_ffs} / {MACHXO2_2000_MAX_FFS} ({tot_ffs / MACHXO2_2000_MAX_FFS * 100:.1f}%)",
                f"- **EBR (9Kb Blocks):** {tot_ebr} / {MACHXO2_2000_MAX_EBR_BLOCKS} ({tot_ebr / MACHXO2_2000_MAX_EBR_BLOCKS * 100:.1f}%)",
            ]
        )
        return "\n".join(lines)


def fpga_resource(
    approach: str,
    luts: int,
    slices_ccu2c: int = 0,
    ffs: int = 0,
    ebr: int = 0,
    dsp: int = 0,
    delay_ns: float = 0.0,
    cycles: int = 1,
    shared_unit: Optional[str] = None,
) -> Callable:
    """Decorator to annotate functions or classes with FPGA resource usage."""

    def decorator(func: Callable) -> Callable:
        resource = FpgaResource(
            approach=approach,
            luts=luts,
            slices_ccu2c=slices_ccu2c,
            ffs=ffs,
            ebr=ebr,
            dsp=dsp,
            delay_ns=delay_ns,
            cycles=cycles,
            shared_unit=shared_unit,
        )
        setattr(func, "__fpga_resource__", resource)
        # Register under function qualified name
        name = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))
        FpgaResourceRegistry.register(name, resource)
        return func

    return decorator

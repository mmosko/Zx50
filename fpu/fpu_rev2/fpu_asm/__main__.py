import argparse
from pathlib import Path
import sys
from typing import List, Optional

from fpu_asm.assembler import Assembler
from fpu_asm.emitter import pad_instructions, write_output, write_symbol_table
from fpu_asm.preprocessor import AssemblerError


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fpu_asm",
        description="Zx50 FPU Microcode Assembler (fasm): Compiles microcode source into binary (.bin), hex (.hex), or Python (.py) ROM images.",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to input microcode assembly file (.fasm or .asm).",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to output file (.bin, .hex, or .py).",
    )
    parser.add_argument(
        "-s",
        "--sym",
        help="Path to write the symbol table report (.sym).",
    )
    parser.add_argument(
        "-I",
        "--include",
        action="append",
        default=[],
        help="Additional include directory for .include resolution (can be repeated).",
    )
    parser.add_argument(
        "--pad",
        type=int,
        default=512,
        help="Pad output image with NOPs up to this number of 32-bit words (default: 512).",
    )
    parser.add_argument(
        "--no-pad",
        action="store_true",
        help="Do not pad with NOPs beyond the highest assembled instruction address.",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "bin", "hex", "py"],
        default="auto",
        help="Output format: 'bin', 'hex', 'py', or 'auto' (inferred from file extension).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_file():
        sys.stderr.write(f"Error: Input file '{args.input}' not found.\n")
        return 1

    assembler = Assembler(include_paths=args.include)

    try:
        program = assembler.assemble_file(input_path)
        total_words = None if args.no_pad else args.pad
        padded_instructions = pad_instructions(program, total_words=total_words)
        write_output(
            padded_instructions,
            args.output,
            format_type=args.format,
            symbols=assembler.symbols,
        )

        print(
            f"Successfully assembled {len(program)} instructions "
            f"(padded to {len(padded_instructions)} words) -> {args.output}"
        )

        if args.sym:
            write_symbol_table(assembler.symbols, args.sym)
            print(f"Wrote symbol table -> {args.sym}")

        return 0

    except AssemblerError as e:
        sys.stderr.write(f"Assembly Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

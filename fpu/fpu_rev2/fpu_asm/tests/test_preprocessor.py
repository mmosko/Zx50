import pytest
from pathlib import Path
from fpu_asm.assembler import Assembler
from fpu_asm.preprocessor import (
    Preprocessor,
    IncludeError,
    CircularIncludeError,
    AssemblySyntaxError,
    UndefinedSymbolError,
)
from fpu_emu.micro_opcodes import MicroOp
from fpu_emu.hardware.reg import Reg


def test_preprocessor_no_includes():
    src = "ADD AL, BL\nHALT\n"
    prep = Preprocessor()
    res = prep.process_string(src, filename="test.fasm")
    assert res.text == "ADD AL, BL\nHALT\n"
    assert len(res.source_map) == 2
    assert res.get_location(1).file_path.name == "test.fasm"
    assert res.get_location(1).line_number == 1
    assert res.get_location(2).line_number == 2


def test_preprocessor_quoted_and_unquoted_includes(tmp_path: Path):
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()

    f1 = sub_dir / "inc1.fasm"
    f1.write_text("MOV DL, BL\n", encoding="utf-8")

    f2 = sub_dir / "inc2.fasm"
    f2.write_text("POP AL\n", encoding="utf-8")

    f3 = sub_dir / "inc3.fasm"
    f3.write_text("PUSH AL\n", encoding="utf-8")

    main = tmp_path / "main.fasm"
    main.write_text(
        'ADD AL, BL\n'
        '.include "sub/inc1.fasm"\n'
        ".include 'sub/inc2.fasm'   ; single quote with comment\n"
        '.include sub/inc3.fasm ; unquoted\n'
        'HALT\n',
        encoding="utf-8",
    )

    prep = Preprocessor()
    res = prep.process_file(main)

    expected_lines = [
        "ADD AL, BL",
        "MOV DL, BL",
        "POP AL",
        "PUSH AL",
        "HALT",
    ]
    assert res.text.strip().splitlines() == expected_lines

    assert res.get_location(1).file_path == main.resolve()
    assert res.get_location(1).line_number == 1

    assert res.get_location(2).file_path == f1.resolve()
    assert res.get_location(2).line_number == 1

    assert res.get_location(3).file_path == f2.resolve()
    assert res.get_location(3).line_number == 1

    assert res.get_location(4).file_path == f3.resolve()
    assert res.get_location(4).line_number == 1

    assert res.get_location(5).file_path == main.resolve()
    assert res.get_location(5).line_number == 5


def test_preprocessor_nested_includes(tmp_path: Path):
    c = tmp_path / "c.fasm"
    c.write_text("RET\n", encoding="utf-8")

    b = tmp_path / "b.fasm"
    b.write_text("CALL c.fasm\n.include c.fasm\n", encoding="utf-8")

    a = tmp_path / "a.fasm"
    a.write_text("NOP\n.include b.fasm\nHALT\n", encoding="utf-8")

    prep = Preprocessor()
    res = prep.process_file(a)

    expected = ["NOP", "CALL c.fasm", "RET", "HALT"]
    assert res.text.strip().splitlines() == expected

    # Line 3 is RET from c.fasm:1
    assert res.get_location(3).file_path == c.resolve()
    assert res.get_location(3).line_number == 1


def test_preprocessor_search_paths(tmp_path: Path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    shared = lib_dir / "shared.fasm"
    shared.write_text("SUB AL, BL\n", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    main = src_dir / "main.fasm"
    main.write_text(".include shared.fasm\n", encoding="utf-8")

    prep = Preprocessor(include_paths=[lib_dir])
    res = prep.process_file(main)
    assert res.text.strip() == "SUB AL, BL"
    assert res.get_location(1).file_path == shared.resolve()


def test_preprocessor_file_not_found(tmp_path: Path):
    main = tmp_path / "main.fasm"
    main.write_text("ADD AL, BL\n.include non_existent.fasm\n", encoding="utf-8")

    prep = Preprocessor()
    with pytest.raises(IncludeError) as exc_info:
        prep.process_file(main)

    err_str = str(exc_info.value)
    assert "Include file not found: 'non_existent.fasm'" in err_str
    assert f"{main.resolve()}:2:" in err_str


def test_preprocessor_circular_include(tmp_path: Path):
    f1 = tmp_path / "f1.fasm"
    f2 = tmp_path / "f2.fasm"

    f1.write_text(".include f2.fasm\n", encoding="utf-8")
    f2.write_text(".include f1.fasm\n", encoding="utf-8")

    prep = Preprocessor()
    with pytest.raises(CircularIncludeError) as exc_info:
        prep.process_file(f1)

    err_str = str(exc_info.value)
    assert "Circular include detected" in err_str
    assert "f1.fasm -> f2.fasm -> f1.fasm" in err_str


def test_preprocessor_malformed_include(tmp_path: Path):
    main = tmp_path / "main.fasm"
    main.write_text(".include\n", encoding="utf-8")

    prep = Preprocessor()
    with pytest.raises(IncludeError) as exc_info:
        prep.process_file(main)

    assert "Malformed .include directive" in str(exc_info.value)


def test_assembler_end_to_end_includes(tmp_path: Path):
    sub = tmp_path / "sub.fasm"
    sub.write_text(
        "sub_routine:\n"
        "    SUB AL, BL\n"
        "    RET\n",
        encoding="utf-8",
    )

    main = tmp_path / "main.fasm"
    main.write_text(
        "entry:\n"
        "    ADD AL, BL\n"
        "    CALL sub_routine\n"
        "    HALT\n"
        ".include sub.fasm\n",
        encoding="utf-8",
    )

    asm = Assembler()
    prog = asm.assemble_file(main)

    assert len(prog) == 5
    assert prog[0][1].op == MicroOp.ADD
    assert prog[1][1].op == MicroOp.CALL
    assert prog[1][1].imm == 3  # sub_routine is at word 3
    assert prog[2][1].op == MicroOp.HALT
    assert prog[3][1].op == MicroOp.SUB
    assert prog[4][1].op == MicroOp.RET


def test_assembler_syntax_error_provenance(tmp_path: Path):
    sub = tmp_path / "broken_sub.fasm"
    sub.write_text(
        "; line 1\n"
        "; line 2\n"
        "SYNTAX ERROR HERE\n",
        encoding="utf-8",
    )

    main = tmp_path / "main.fasm"
    main.write_text(
        "ADD AL, BL\n"
        ".include broken_sub.fasm\n"
        "HALT\n",
        encoding="utf-8",
    )

    asm = Assembler()
    with pytest.raises(AssemblySyntaxError) as exc_info:
        asm.assemble_file(main)

    err_str = str(exc_info.value)
    # Must report line 3 of broken_sub.fasm, not line 4 of combined file!
    assert str(sub.resolve()) in err_str
    assert f"{sub.resolve()}:3:" in err_str


def test_assembler_undefined_symbol_provenance(tmp_path: Path):
    sub = tmp_path / "bad_sym.fasm"
    sub.write_text(
        "JMP MISSING_LABEL\n",
        encoding="utf-8",
    )

    main = tmp_path / "main.fasm"
    main.write_text(
        "NOP\n"
        "NOP\n"
        ".include bad_sym.fasm\n",
        encoding="utf-8",
    )

    asm = Assembler()
    with pytest.raises(UndefinedSymbolError) as exc_info:
        asm.assemble_file(main)

    err_str = str(exc_info.value)
    # Must report line 1 of bad_sym.fasm
    assert str(sub.resolve()) in err_str
    assert f"{sub.resolve()}:1:" in err_str
    assert "MISSING_LABEL" in err_str

The purpose of this Python code is to have an accurate machine model for the FPU that will be written
in Verilog. Do not cheat the rules. Cheating invalidates the whole purpose of the code.

- BANNED: Importing or using the Python `math` module.
- BANNED: High-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- BANNED: Procedural hard-coded calculation shortcuts or python loops bypassing microcode.
- REQUIRED: All arithmetic, scaling, table queries, and stack moves execute cycle-by-cycle
  via `run_microcode()` and the 16-bit synthesizable ALU primitive.

- Register access must be through the HA_BUS and HB_BUS max
- Register write-back must be through the RES_BUS mux
- Must obey MachXO2-2000 flipflop timing for write-backs
- Must obey MachX02-2000 EBR memory access rules
- Nothing should access the private register members directly except the tests/testharness.py or the existing
  APIs in registers.py.
- Do not modify registers.py without approval. This is to prevent the AI from cheating the rules.

### Microcode

We are switching to per-UserOpcode source in fpu_emu/asm and they are included in fpu_emu/ucode.asm.
The microcode is compiled with this, to emit Python code for easy integration into the emulator.

```bash
   python3 -m fpu_asm -i fpu_emu/ucode.asm -o fpu_emu/ucode.py
```

### Code Checking Protocol

Execute the following verification steps in order. If any step fails, resolve the issue and restart from Step 1.

- **Ban Dynamic getattr:** Run `bash tools/check_no_getattr.sh` (Ensures zero usage of `getattr()` in production code).
1. **Format & Lint:** Run `ruff check --fix .` and `ruff format .` (Fix all errors and eliminate warnings).
2. **Type Check:** Run `pyright` (Ensure zero type errors).
3. **Tests & Coverage:** Run `pytest --xdoctest --cov=src --cov-fail-under=90` (Executes unit tests, verifies docstring
   code blocks, and enforces 90% code coverage).
4. **Complexity:** Ensure cyclomatic complexity remains under 12. Ruff rule `C901` will flag violations; use
   `# noqa: C901` only for necessary exceptions (e.g., large dispatcher/match statements).
5. **Dead Code Check:** Run `vulture --exclude tests --exclude .venv .` (Identify dead code or unused imports; ignore
   intentionally uncalled public API entry points).
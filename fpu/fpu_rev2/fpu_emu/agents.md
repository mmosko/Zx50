The purpose of this Python code is to have an accurate machine model for the FPU that will be written
in Verilog.  Do not cheat the rules.  Cheating invalidates the whole purpose of the code.

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
- Do not modify registers.py without approval.  This is to prevent the AI from cheating the rules.

Code Checking
- Use pytest to ensure all tests pass
- Use pytest --cov and aim for at least 90% coverage
- Use ruff and fix all errors, try to avoid warnings
- Target cyclomatic complexity less than 12 (exceptions are OK, such as the dispatcher switch)
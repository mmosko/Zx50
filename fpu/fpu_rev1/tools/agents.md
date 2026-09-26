
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Executes operations exclusively via microcode step sequences and Flash ROM LUTs.

CPLD HARDWARE RULES:
- BANNED: Importing or using the Python `math` module.
- BANNED: High-level Python arithmetic operators (*, /, //, %, **) in algorithm paths.
- BANNED: Procedural hard-coded calculation shortcuts or python loops bypassing microcode.
- REQUIRED: All arithmetic, scaling, table queries, and stack moves execute cycle-by-cycle
  via `run_microcode()` and the 16-bit synthesizable ALU primitive.
- Operands in $NOS$ ($a_0..a_3$) and $TOS$ ($b_0..b_3$) must not be overwritten until ALL
  cross-product passes requiring those bytes have finished reading.

Strict CPLD Hardware Rules
- Hardware Register Limits: The CPLD contains only ACC (8-bit), OPB (8-bit), TMP0 (16-bit), TMP1 (16-bit),
  BYTE_CNT (2-bit), and U_PC (7-bit).
- Zero Python Procedural Math: High-level operators (*, //, +, %, procedural for loops) are banned inside
  execute_opcode() or algorithm paths.
- SRAM Scratchpad Offloading: All intermediate partial products, multi-byte carries, and accumulation passes must
  read from and write to reserved SRAM scratchpad bytes (0x0000–0x0007).

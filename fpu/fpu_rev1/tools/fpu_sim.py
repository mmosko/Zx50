#!/usr/bin/env python3
"""
ZX50 FPU Coprocessor Microcode & Datapath Simulator
Simulates the ATF1508AS CPLD micro-engine, private SRAM/Flash, and ALU.
Executes operations exclusively via microcode step sequences and Flash ROM LUTs.

Read `agents.md` for rules
"""
from zx50_fpu_machine import ZX50FPUMachine


# =============================================================================
# Verification Test Suite
# =============================================================================
def main():
    fpu = ZX50FPUMachine()
    print("=================================================")
    print("=== ZX50 Microcode Simulator Execution Tests  ===")
    print("=================================================")

    # Test 1: I32 Addition (0x12345678 + 0x00112233 = 0x124578AB) -> Opcode 0x10
    fpu.push_nos_i32(0x12345678)
    fpu.push_tos_i32(0x00112233)
    fpu.execute_opcode(0x10)  # FMT_I32 | OP_ADD
    res_add = fpu.read_nos_i32() & 0xFFFFFFFF
    assert res_add == 0x124578AB, f"I32_ADD Failed: {hex(res_add)}"
    print(f"PASS [I32_ADD]:     0x12345678 + 0x00112233 = 0x{res_add:08X}")

    # Test 2: FX1616 Addition (1.5 + 2.5 = 4.0) -> Opcode 0x30
    fpu.push_nos_fx1616(1.5)
    fpu.push_tos_fx1616(2.5)
    fpu.execute_opcode(0x30)  # FMT_FX1616 | OP_ADD
    res_fx = fpu.read_nos_fx1616()
    assert abs(res_fx - 4.0) < 1e-4, f"FX1616_ADD Failed: {res_fx}"
    print(f"PASS [FX1616_ADD]:  1.5 + 2.5 = {res_fx}")

    print("=================================================")
    print("===  UNIFORM 32-BIT MICROCODE TESTS PASSED!   ===")
    print("=================================================")


if __name__ == "__main__":
    main()

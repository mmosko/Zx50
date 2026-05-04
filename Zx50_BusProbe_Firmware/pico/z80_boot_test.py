# z80_boot_test.py
import time
import bus

def _do_cmd(pic, args, output):
    response = pic.handle_command(args)
    if response.startswith("OK"):
        return response
    else:
        pic.handle_command(["CLK_STOP"])
        pic.handle_command(["GHOST", "1"])
        msg = f">> FAILED: cmd {args} response '{response}'"
        output(msg)
        raise RuntimeError(msg)

def format_eta(seconds):
    if seconds < 0:
        return "Calculating..."
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"

def run(pic, bus_mgr, output):
    """
    Validates the 32KB Cold-Boot ROM window, then tests the MMU trapdoor.
    """
    CARD_ID = 0  
    BASE_PORT = 0x30 | CARD_ID
    MAGIC_STRING = b"Zx50 Hello World!\0"
    
    # Based on page_ownership = 0x00FF, we only own 8 pages (32KB)
    BOOT_WINDOW_BYTES = 32768 
    total_errors = 0

    output(f">> Z80 Script: Initializing 32KB Boot ROM Window Test...")

    # Ensure safe starting state (Hardware Reset State)
    bus_mgr.ghost_all()
    _do_cmd(pic, ["GHOST", "0"], output)
    _do_cmd(pic, ["CLK_START"], output)

    # ==========================================
    # TEST 1: Verifying the 32KB Boot Window
    # ==========================================
    output(f"\n>> TEST 1: Verifying 32KB ROM window (NO MMU WRITES)...")
    
    start_time = time.time()
    test1_errors = 0

    for logical_addr in range(BOOT_WINDOW_BYTES):
        # Check for the Magic String at the very beginning
        if logical_addr < len(MAGIC_STRING):
            expected_val = MAGIC_STRING[logical_addr]
        else:
            # Check the ROM hash (0x75) for the rest of the 32KB
            expected_val = (logical_addr ^ (logical_addr >> 8) ^ (logical_addr >> 16) ^ 0x75) & 0xFF
        
        resp = pic.handle_command(["READ", f"{logical_addr:04X}"])

        if resp.startswith("OK"):
            val = int(resp.split()[1], 16)
            if val != expected_val:
                output(f"   [FAIL] ROM Mismatch at {logical_addr:04X}. Expected {expected_val:02X}, read {val:02X}.")
                test1_errors += 1
        else:
            output(f"   [FAIL] READ ERROR at {logical_addr:04X}: '{resp}'")
            test1_errors += 1

        if test1_errors > 50:
            output(">> FATAL: Too many ROM verification errors. Aborting.")
            break

        if logical_addr > 0 and logical_addr % 4096 == 0:
            elapsed = time.time() - start_time
            speed = logical_addr / elapsed
            eta = (BOOT_WINDOW_BYTES - logical_addr) / speed
            output(f"  ... Verified Boot ROM up to {logical_addr:04X} [Speed: {speed:.0f} B/s | ETA: {format_eta(eta)}]")

    total_errors += test1_errors
    
    if test1_errors == 0:
        output("   [PASS] 32KB Cold-Boot ROM Window successfully verified!")
    else:
        output(f"   [FAIL] Test 1 completed with {test1_errors} errors.")

    # ==========================================
    # TEST 2: Trigger the Trapdoor
    # ==========================================
    # We proceed to Test 2 even if Test 1 failed, to see if the hardware MMU works at all.
    output("\n>> TEST 2: Triggering MMU Trapdoor (Mapping RAM Page 0 to Logical 0)...")
    
    logical_page = 0
    physical_page = 0
    port_addr = (logical_page << 12) | BASE_PORT
    _do_cmd(pic, ["OUT", f"{port_addr:04X}", f"{physical_page:02X}"], output)
    
    output("   [DONE] MMU updated. ROM_EN should now be permanently disabled.")

    # ==========================================
    # TEST 3: Verify SRAM is now active at 0x0000
    # ==========================================
    output("\n>> TEST 3: Verifying SRAM Handoff at 0x0000...")

    test_pattern = [0xDE, 0xAD, 0xBE, 0xEF, 0x55, 0xAA, 0x12, 0x34]
    
    output("   Writing fresh test pattern to SRAM...")
    for offset, val in enumerate(test_pattern):
        _do_cmd(pic, ["WRITE", f"{offset:04X}", f"{val:02X}"], output)

    test3_errors = 0
    for offset, expected_val in enumerate(test_pattern):
        resp = pic.handle_command(["READ", f"{offset:04X}"])
        if resp.startswith("OK"):
            val = int(resp.split()[1], 16)
            if val != expected_val:
                output(f"   [FAIL] SRAM Mismatch at {offset:04X}. Expected {expected_val:02X}, read {val:02X}.")
                test3_errors += 1
        else:
            output(f"READ ERROR at {offset:04X}: {resp}")
            test3_errors += 1

    total_errors += test3_errors

    if test3_errors == 0:
        output("   [PASS] Wrote and read back the exact SRAM test pattern!")
        output("   [PASS] EEPROM successfully yielded the bus to SRAM.")
    else:
        output(f"   [FAIL] Test 3 completed with {test3_errors} errors.")

    # Shutdown sequence
    pic.handle_command(["CLK_STOP"])
    pic.handle_command(["GHOST", "1"])

    # ==========================================
    # FINAL RESULTS
    # ==========================================
    if total_errors == 0:
        output("\n>> SUCCESS: 32KB ROM Boot Window & MMU Handoff fully validated!")
        return "PASS"
    else:
        output(f"\n>> FAILED: Validation finished with {total_errors} total errors.")
        return "FAIL"


# z80_rom_test.py
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

def run(pic, bus_mgr, output):
    """
    Stress-tests the 32KB Cold-Boot ROM window by looping 100 times.
    Halts on the very first read error. NO MMU OPERATIONS.
    """
    MAGIC_STRING = b"Zx50 Hello World!\0"
    BOOT_WINDOW_BYTES = 32768 
    MAX_LOOPS = 100

    output(f">> Z80 Script: Initializing 32KB ROM Stress Test ({MAX_LOOPS} Loops)...")

    # Ensure safe starting state
    bus_mgr.ghost_all()
    _do_cmd(pic, ["GHOST", "0"], output)
    _do_cmd(pic, ["CLK_START"], output)

    total_start_time = time.time()

    for loop_count in range(1, MAX_LOOPS + 1):
        output(f"\n>> Starting Loop {loop_count}/{MAX_LOOPS}...")
        
        loop_start_time = time.time()
        errors = 0

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
                    errors += 1
            else:
                output(f"   [FAIL] READ ERROR at {logical_addr:04X}: '{resp}'")
                errors += 1

            # Stop on the very first failure
            if errors > 0:
                output(f">> FATAL: Failure detected on Loop {loop_count}. Aborting.")
                break

            # Print a heartbeat every 8KB so we know it's still alive
            if logical_addr > 0 and logical_addr % 8192 == 0:
                elapsed = time.time() - loop_start_time
                speed = logical_addr / elapsed
                output(f"  ... Verified up to {logical_addr:04X} [Speed: {speed:.0f} B/s]")

        if errors > 0:
            # Clean up bus and hard exit
            pic.handle_command(["CLK_STOP"])
            pic.handle_command(["GHOST", "1"])
            return "FAIL"
            
        loop_time = time.time() - loop_start_time
        output(f"   [PASS] Loop {loop_count} completed flawlessly in {loop_time:.1f}s.")

    # Shutdown sequence after 100 successful loops
    pic.handle_command(["CLK_STOP"])
    pic.handle_command(["GHOST", "1"])

    total_time = time.time() - total_start_time
    output(f"\n>> SUCCESS: 32KB ROM verified {MAX_LOOPS} times without a single error! ({total_time:.1f}s total)")
    return "PASS"


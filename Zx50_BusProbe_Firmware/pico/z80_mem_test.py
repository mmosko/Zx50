# z80_mem_test.py
import time
from collections import deque
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
    """Returns a nicely formatted ETA string."""
    if seconds < 0:
        return "Calculating..."
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"

def run(pic, bus_mgr, output):
    """
    Executes a comprehensive 1MB Memory Card test.
    Tests all 256 physical pages (1MB) by mapping them into the Z80's 64KB window.
    """
    CARD_ID = 3
    BASE_PORT = 0x30 | CARD_ID
    TOTAL_PHYSICAL_PAGES = 256
    PAGES_PER_WINDOW = 16
    BYTES_PER_PAGE = 4096
    
    # Total bytes to process (1MB)
    TOTAL_BYTES = TOTAL_PHYSICAL_PAGES * BYTES_PER_PAGE 

    output(f">> Z80 Script: Initializing 1MB Memory Card {CARD_ID} Test...")

    # Ensure safe starting state
    bus_mgr.ghost_all()
    _do_cmd(pic, ["GHOST", "0"], output)
    _do_cmd(pic, ["CLK_START"], output)

    # ==========================================
    # PHASE 1: Write to all 1MB
    # ==========================================
    output(f">> PHASE 1: Writing 1MB using 20-bit hashing...")
    
    start_time = time.time()
    bytes_written = 0
    errors = 0
    
    for window_start_page in range(0, TOTAL_PHYSICAL_PAGES, PAGES_PER_WINDOW):
        
        # 1. Map the 16 physical pages into logical pages 0-15
        for logical_page in range(PAGES_PER_WINDOW):
            physical_page = window_start_page + logical_page
            port_addr = (logical_page << 12) | BASE_PORT
            _do_cmd(pic, ["OUT", f"{port_addr:04X}", f"{physical_page:02X}"], output)

        # 2. Write to the newly mapped 64KB window
        for logical_page in range(PAGES_PER_WINDOW):
            physical_page = window_start_page + logical_page
            base_physical_addr = physical_page * BYTES_PER_PAGE
            
            for offset in range(BYTES_PER_PAGE):
                logical_addr = (logical_page * BYTES_PER_PAGE) + offset
                physical_addr = base_physical_addr + offset
                
                # The 20-bit Physical Hash
                val = (physical_addr ^ (physical_addr >> 8) ^ (physical_addr >> 16) ^ 0x5A) & 0xFF
                
                resp = pic.handle_command(["WRITE", f"{logical_addr:04X}", f"{val:02X}"])
                
                if not resp.startswith("OK"):
                    output(f"WRITE ERROR at Physical 0x{physical_addr:05X} (Logical 0x{logical_addr:04X}): {resp}")
                    errors += 1
                    if errors > 50:
                        break
                
                bytes_written += 1
            
            if errors > 50:
                 break
                 
            # GLOBAL ETA CALCULATION
            elapsed_time = time.time() - start_time
            bytes_per_sec = bytes_written / elapsed_time
            
            # Remaining writes take 1x time. The 1MB of reads takes 2x time.
            remaining_writes = TOTAL_BYTES - bytes_written
            equivalent_bytes_remaining = remaining_writes + (TOTAL_BYTES * 2)
            
            eta_seconds = equivalent_bytes_remaining / bytes_per_sec if bytes_per_sec > 0 else -1
            
            output(f"  ... Written Page {physical_page:03d}/255 [Write Speed: {bytes_per_sec:.0f} B/s | Global ETA: {format_eta(eta_seconds)}]")
            
        if errors > 50:
            output(">> FATAL: Too many write errors. Aborting.")
            break

    write_time = time.time() - start_time
    output(f">> Write phase complete in {write_time:.1f} seconds. ({TOTAL_BYTES / write_time:.0f} B/s)")


    # ==========================================
    # PHASE 2: Verify all 1MB
    # ==========================================
    if errors == 0:
        output(f"\n>> PHASE 2: Verifying 1MB...")
        start_time = time.time()
        bytes_read = 0
        
        for window_start_page in range(0, TOTAL_PHYSICAL_PAGES, PAGES_PER_WINDOW):
            
            # 1. Map the 16 physical pages into logical pages 0-15
            for logical_page in range(PAGES_PER_WINDOW):
                physical_page = window_start_page + logical_page
                port_addr = (logical_page << 12) | BASE_PORT
                _do_cmd(pic, ["OUT", f"{port_addr:04X}", f"{physical_page:02X}"], output)

            # 2. Read from the mapped window
            for logical_page in range(PAGES_PER_WINDOW):
                physical_page = window_start_page + logical_page
                base_physical_addr = physical_page * BYTES_PER_PAGE
                
                for offset in range(BYTES_PER_PAGE):
                    logical_addr = (logical_page * BYTES_PER_PAGE) + offset
                    physical_addr = base_physical_addr + offset
                    
                    expected_val = (physical_addr ^ (physical_addr >> 8) ^ (physical_addr >> 16) ^ 0x5A) & 0xFF
                    
                    resp = pic.handle_command(["READ", f"{logical_addr:04X}"])

                    if resp.startswith("OK"):
                        try:
                            read_val = int(resp.split()[1], 16)
                            if read_val != expected_val:
                                output(f"MISMATCH at Physical 0x{physical_addr:05X} (Logical 0x{logical_addr:04X}): Expected 0x{expected_val:02X}, Read 0x{read_val:02X}")
                                errors += 1
                        except IndexError:
                            output(f"PARSE ERROR at Physical 0x{physical_addr:05X}: Response was '{resp}'")
                            errors += 1
                    else:
                        output(f"READ ERROR at Physical 0x{physical_addr:05X}: Response was '{resp}'")
                        errors += 1

                    bytes_read += 1
                    if errors > 50:
                        break
                        
                if errors > 50:
                    break
                    
                # Display ETA after every 4KB page (In Phase 2, Global ETA is just Phase 2 ETA)
                elapsed_time = time.time() - start_time
                bytes_per_sec = bytes_read / elapsed_time
                bytes_remaining = TOTAL_BYTES - bytes_read
                eta_seconds = bytes_remaining / bytes_per_sec if bytes_per_sec > 0 else -1
                
                output(f"  ... Verified Page {physical_page:03d}/255 [Read Speed: {bytes_per_sec:.0f} B/s | Global ETA: {format_eta(eta_seconds)}]")

            if errors > 50:
                output(">> FATAL: Too many verify errors. Aborting.")
                break

        read_time = time.time() - start_time
        output(f">> Verify phase complete in {read_time:.1f} seconds. ({TOTAL_BYTES / read_time:.0f} B/s)")

    # Shutdown sequence
    pic.handle_command(["CLK_STOP"])
    pic.handle_command(["GHOST", "1"])

    # ==========================================
    # RESULTS
    # ==========================================
    if errors == 0:
        output("\n>> SUCCESS: Entire 1MB (256 Pages) passed verification!")
        output(">> The Backplane, MMU, and 1MB SRAM are 100% healthy.")
        return "PASS"
    else:
        output(f"\n>> FAILED with {errors} errors.")
        return "FAIL"


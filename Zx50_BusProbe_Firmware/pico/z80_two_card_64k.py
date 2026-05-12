# z80_two_card_64k.py
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
    Validates dual-card MMU handoffs by mapping even logical pages
    to Card 0x30 and odd logical pages to Card 0x31.
    """
    CARD_0_PORT = 0x30
    CARD_1_PORT = 0x31

    output(f">> Z80 Script: Initializing Interleaved Dual-Card Test...")

    # Ensure safe starting state
    bus_mgr.ghost_all()
    _do_cmd(pic, ["GHOST", "0"], output)
    _do_cmd(pic, ["CLK_START"], output)

    # ==========================================
    # PHASE 1: Interleaved MMU Configuration
    # ==========================================
    output(">> Mapping Logical Pages: Evens -> 0x30, Odds -> 0x31...")

    for logical_page in range(16):
        # Even pages to Card 0, Odd pages to Card 1
        target_port = CARD_0_PORT if (logical_page % 2 == 0) else CARD_1_PORT

        port_addr = (logical_page << 12) | target_port
        physical_page = logical_page  # Map 1:1 physically just for simplicity

        port_hex = f"0x{port_addr:04X}"
        val_hex = f"0x{physical_page:02X}"

        output(f"   Mapping Logical Page {logical_page:02d} to Port {target_port:02X} (Phys Page {physical_page:02X})")
        _do_cmd(pic, ["OUT", port_hex, val_hex], output)

    # Give the MMUs a tiny delay to settle
    time.sleep(0.01)

    # ==========================================
    # PHASE 2: Write the Hashed Pattern to 64K
    # ==========================================
    output("\n>> Writing hashed pattern across both cards (64KB)...")
    start_time = time.time()

    for addr in range(65536):
        # Create a unique byte based on the address
        val = (addr ^ (addr >> 8)) & 0xFF

        addr_hex = f"0x{addr:04X}"
        val_hex = f"0x{val:02X}"

        _do_cmd(pic, ["WRITE", addr_hex, val_hex], output)

        if addr % 8192 == 0 and addr > 0:
            active_card = "0x30" if (addr // 4096) % 2 == 0 else "0x31"
            output(f"  ... Written up to {addr_hex} (Active Card: {active_card})")

    write_time = time.time() - start_time
    output(f">> Write phase complete in {write_time:.1f} seconds.")

    # ==========================================
    # PHASE 3: Read and Verify 64K
    # ==========================================
    output("\n>> Verifying Dual-Card Data Integrity...")
    start_time = time.time()
    errors = 0

    for addr in range(65536):
        expected_val = (addr ^ (addr >> 8)) & 0xFF
        addr_hex = f"0x{addr:04X}"

        resp = pic.handle_command(["READ", addr_hex])

        if resp.startswith("OK"):
            try:
                read_val = int(resp.split()[1], 16)
                if read_val != expected_val:
                    output(f"   [FAIL] Mismatch at {addr_hex}: Expected 0x{expected_val:02X}, Read 0x{read_val:02X}")
                    errors += 1
            except IndexError:
                output(f"   [FAIL] Parse Error at {addr_hex}: Response '{resp}'")
                errors += 1
        else:
            output(f"   [FAIL] Read Error at {addr_hex}: Response '{resp}'")
            errors += 1

        if errors > 50:
            output(">> FATAL: Too many errors detected. Aborting test.")
            break

        if addr % 8192 == 0 and addr > 0:
            active_card = "0x30" if (addr // 4096) % 2 == 0 else "0x31"
            output(f"  ... Verified up to {addr_hex} (Active Card: {active_card})")

    read_time = time.time() - start_time
    output(f">> Verify phase complete in {read_time:.1f} seconds.")

    # Clean shutdown
    pic.handle_command(["CLK_STOP"])
    pic.handle_command(["GHOST", "1"])

    # ==========================================
    # RESULTS
    # ==========================================
    if errors == 0:
        output(f"\n>> SUCCESS: 64KB Dual-Card Interleaved Test Passed! ({write_time + read_time:.1f}s total)")
        return "PASS"
    else:
        output(f"\n>> FAILED: Found {errors} errors during dual-card verification.")
        return "FAIL"

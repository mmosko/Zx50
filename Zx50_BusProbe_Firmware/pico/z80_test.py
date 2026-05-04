# z80_test.py
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

def run(pic, bus, output):
    """
    Executes a custom sequence of Z80 bus operations to validate a 64K Memory Card.
    """
    # Set this to the DIP switch ID of your card (0-3)
    CARD_ID = 3
    BASE_PORT = 0x30 | CARD_ID

    output(f">> Z80 Script: Initializing Memory Card {CARD_ID} MMU...")

    # Ensure safe starting state
    bus.ghost_all()
    _do_cmd(pic, ["GHOST", "0"], output)
    _do_cmd(pic, ["CLK_START"], output)

    # ==========================================
    # PHASE 1: Initialize the MMU (Linear 1:1 Mapping)
    # ==========================================
    output(">> Mapping 16 Logical Pages -> Physical Pages...")
    for logical_page in range(16):
        # Z80 I/O addressing: Upper 8 bits (A15-A8) carry the logical page,
        # lower 8 bits carry the target port.
        port_addr = (logical_page << 12) | BASE_PORT
        physical_page = logical_page

        port_hex = f"0x{port_addr:04X}"
        val_hex = f"0x{physical_page:02X}"

        _do_cmd(pic, ["OUT", port_hex, val_hex], output)

    # Give the hardware a tiny delay to settle
    time.sleep(0.01)

    # ==========================================
    # PHASE 2: Write the Hashed Pattern to 64K
    # ==========================================
    output(">> Writing hashed values to 64K RAM...")
    start_time = time.time()

    for addr in range(65536):
        # 16-bit address hash (addr >> 16 is implicitly 0)
        val = (addr ^ (addr >> 8)) & 0xFF

        addr_hex = f"0x{addr:04X}"
        val_hex = f"0x{val:02X}"

        _do_cmd(pic, ["WRITE", addr_hex, val_hex], output)

        if addr % 8192 == 0 and addr > 0:
            output(f"  ... Written up to {addr_hex}")

    write_time = time.time() - start_time
    output(f">> Write phase complete in {write_time:.1f} seconds.")

    # ==========================================
    # PHASE 3: Read and Verify 64K
    # ==========================================
    output(">> Verifying 64K RAM...")
    start_time = time.time()
    errors = 0

    for addr in range(65536):
        expected_val = (addr ^ (addr >> 8)) & 0xFF
        addr_hex = f"0x{addr:04X}"

        # 'pic.handle_command' returns a string like "OK C3" or "ERR ..."
        resp = pic.handle_command(["READ", addr_hex])

        if resp.startswith("OK"):
            try:
                # Extract the hex byte from the response
                read_val = int(resp.split()[1], 16)
                if read_val != expected_val:
                    output(f"MISMATCH at {addr_hex}: Expected 0x{expected_val:02X}, Read 0x{read_val:02X}")
                    errors += 1
            except IndexError:
                output(f"PARSE ERROR at {addr_hex}: Response was '{resp}'")
                errors += 1
        else:
            output(f"READ ERROR at {addr_hex}: Response was '{resp}'")
            errors += 1

        # Abort if the bus is completely unresponsive to save time
        if errors > 50:
            output(">> FATAL: Too many errors. Aborting verification to save time.")
            break

        if addr % 8192 == 0 and addr > 0:
            output(f"  ... Verified up to {addr_hex}")

    read_time = time.time() - start_time
    output(f">> Verify phase complete in {read_time:.1f} seconds.")

    pic.handle_command(["CLK_STOP"])
    pic.handle_command(["GHOST", "1"])

    # ==========================================
    # RESULTS
    # ==========================================
    if errors == 0:
        output("\n>> SUCCESS: Entire 64K RAM passed verification!")
        output(">> The Backplane, MMU, and SRAM are 100% healthy.")
        return "PASS"
    else:
        output(f"\n>> FAILED: Found {errors} errors.")
        return "FAIL"
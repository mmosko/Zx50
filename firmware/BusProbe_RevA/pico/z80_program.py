import time


def run(pic, bus):
    """
    Programs the MMU for Card 1 to own all 16 logical pages.
    """
    print(">> Z80 Script: Initializing Card 1 MMU...")

    # Ensure the PIC is actively driving the bus
    pic.handle_command(["GHOST", "0"])

    # -------------------------------------------------------------------------
    # BUS RESET NOTE:
    # pic18_link.py currently lacks a dedicated software RESET command.
    # If your PIC firmware supports it later, you would call: pic.handle_command(["RESET"])
    #
    # REMINDER: To latch as Card 1, the backplane must have MREQ=0, IORQ=0, RD=0, WR=1
    # at the exact moment the ~RESET~ signal rises!
    # -------------------------------------------------------------------------
    time.sleep(0.01)

    print(">> Mapping Logical Pages 0x0-0xF to Physical Pages 0x00-0x0F for Card 1...")

    success = True
    for logical_page in range(16):
        # Format the 16-bit IO port:
        # A11-A8: Logical Page (0x0 to 0xF)
        # A7-A0 : Base MMU Port for Card 1 (0x31)
        port = f"0x{logical_page:X}31"

        # The data byte is the physical page index to store in the ATL SRAM (0x00 to 0x0F)
        phys_page = f"0x{logical_page:02X}"

        resp = pic.handle_command(["OUT", port, phys_page])
        if "OK" not in resp:
            print(f"  [!] Failed to map page {logical_page:X}: {resp}")
            success = False
        else:
            print(f"  [-] Mapped Logical Page {logical_page:X} -> Physical Page {phys_page} (Port {port})")

    time.sleep(0.01)

    # Quick bus verification to see if the SRAM responds
    print("\n>> Memory Mapping Complete. Running quick read/write test...")
    pic.handle_command(["WRITE", "0x0000", "0x42"])
    verify = pic.handle_command(["READ", "0x0000"])

    if "0x42" in verify:
        return "SUCCESS - Card 1 MMU mapped and SRAM readback verified!"
    elif success:
        return "WARNING - MMU mapping succeeded, but SRAM readback failed."
    else:
        return "FAILED - Errors occurred during MMU configuration."

# z80_test.py
import time

def run(pic, bus):
    """
    Executes a custom sequence of Z80 bus operations.
    :param pic: PIC18Link instance to control the Z80 bus
    :param bus: BusController instance to route the multiplexers
    """
    print(">> Z80 Script: Initializing Memory Card MMU...")

    # Ensure safe starting state
    bus.ghost_all()

    # TEST 1: Map Physical Page 0x85 to Logical Page 0
    # Equivalent to sending CLI: pic out 0x30 0x85
    # (Card 0 | Port 0x30 = 0x30)
    print(">> Mapping Physical Page 0x85 to Logical Page 0...")
    resp = pic.handle_command(["OUT", "0x30", "0x85"])
    print(f">> MMU Map Response: {resp}")

    # Give the bus/PIC a tiny delay
    time.sleep(0.01)

    # TEST 2: Write a byte to RAM and read it back
    print(">> Writing 0xAA to address 0x0000...")
    resp_write = pic.handle_command(["WRITE", "0x0000", "0xAA"])
    print(f">> Write Response: {resp_write}")

    print(">> Reading from address 0x0000...")
    resp_read = pic.handle_command(["READ", "0x0000"])
    print(f">> Read Response: {resp_read}")

    # You can return a string that will be printed by the CLI when finished
    if "0xAA" in resp_read:
        return "SUCCESS - Memory Mapped and Verified"
    else:
        return "FAILED - Data Mismatch"
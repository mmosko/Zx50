# generate_eeprom_bin.py

# Creates a test pattern for an EEPROM to validate memory reads on the card.

EEPROM_SIZE = 512 * 1024  # 512 KB

def write_magic_string():
    # Create a bytearray to hold the data
    data = bytearray(EEPROM_SIZE)
    MAGIC_STRING = b"Zx50 Hello World!\0"
    # Fill the entire array with the 20-bit physical hash
    for physical_addr in range(EEPROM_SIZE):
        val = (physical_addr ^ (physical_addr >> 8) ^ (physical_addr >> 16) ^ 0x75) & 0xFF
        data[physical_addr] = val
    # Overwrite the very beginning with our magic string
    for i, char in enumerate(MAGIC_STRING):
        data[i] = char

    print(f"Header: {MAGIC_STRING.decode('ascii')}")
    print(f"Hash seed: 0x75")
    return data

def write_zeros():
    # Create a bytearray to hold the data
    data = bytearray(EEPROM_SIZE)
    for physical_addr in range(EEPROM_SIZE):
        data[physical_addr] = 0
    print(f"Created all no-op data")
    return data


FILENAME = "eeprom_zeros.bin"
data = write_zeros()
# Write the binary file to disk
with open(FILENAME, "wb") as f:
    f.write(data)

print(f"Successfully generated {FILENAME} ({len(data)} bytes)")

FILENAME = "eeprom_magic_string.bin"
data = write_magic_string()
# Write the binary file to disk
with open(FILENAME, "wb") as f:
    f.write(data)

print(f"Successfully generated {FILENAME} ({len(data)} bytes)")

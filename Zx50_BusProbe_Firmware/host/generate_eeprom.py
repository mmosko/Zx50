# generate_eeprom_bin.py

# Creates a test pattern for an EEPROM to validate memory reads on the card.

EEPROM_SIZE = 512 * 1024  # 512 KB
FILENAME = "eeprom_test.bin"
MAGIC_STRING = b"Zx50 Hello World!\0"

# Create a bytearray to hold the data
data = bytearray(EEPROM_SIZE)

# Fill the entire array with the 20-bit physical hash
for physical_addr in range(EEPROM_SIZE):
    val = (physical_addr ^ (physical_addr >> 8) ^ (physical_addr >> 16) ^ 0x75) & 0xFF
    data[physical_addr] = val

# Overwrite the very beginning with our magic string
for i, char in enumerate(MAGIC_STRING):
    data[i] = char

# Write the binary file to disk
with open(FILENAME, "wb") as f:
    f.write(data)

print(f"Successfully generated {FILENAME} ({len(data)} bytes)")
print(f"Header: {MAGIC_STRING.decode('ascii')}")
print(f"Hash seed: 0x75")
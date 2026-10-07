# Zx50 Diagnostic Test ROMs

Graduated, minimal test ROMs designed to isolate hardware subsystems one by one directly from EEPROM. None of these test ROMs use interrupts, stacks, or complex paging initially, making them ideal for single-stepping or logic analyzer debugging.

All commands below should be run from the repository root (`zx50_monitor/`).

### Quick Build: Assemble All Test ROMs
```bash
for rom in testroms/*.z80; do sjasmplus --fullpath --lst="${rom%.z80}.lst" --sld="${rom%.z80}.sld" --sym="${rom%.z80}.sym" "$rom"; done
```

---

## 1. `1-lcd_only.z80` (`1-lcd_only.bin`, 35 bytes)
* **Goal:** Verify CPU execution from EEPROM and Front Panel LCD communication.
* **Dependencies:** None (No RAM, No Stack, No Interrupts, No SIO, No CTC).
* **Behavior:**
  1. Executes `DI` at `0x0000`.
  2. Waits ~170ms for the Raspberry Pi Pico Front Panel to finish cold boot.
  3. Uses `OTIR` to send `"Hello Zx50\n"` to LCD Port `0x50`.
  4. Executes `HALT` (CPU halts and asserts `~HALT` low).
* **Assemble Command:**
  ```bash
  sjasmplus --fullpath --lst=testroms/1-lcd_only.lst --sld=testroms/1-lcd_only.sld --sym=testroms/1-lcd_only.sym testroms/1-lcd_only.z80
  ```
* **Flash Command:**
  ```bash
  minipro -p SST39SF040 -w 1-lcd_only.bin -s
  ```

---

## 2. `2-serial_tx_polled.z80` (`2-serial_tx_polled.bin`, 171 bytes)
* **Goal:** Verify CTC Channel 0 baud rate generation and SIO Channel A transmit to the FTDI USB console.
* **Dependencies:** None (Pure polled I/O, No RAM, No Stack, No Interrupts).
* **Behavior:**
  1. Displays `"Serial Tx Test...\n"` on Front Panel LCD.
  2. Programs CTC Channel 0 (`0x80`) in Counter Mode with `TC = 1` (divides onboard 1.8432 MHz oscillator to 1.8432 MHz).
  3. Programs SIO Channel A (`0x86`) for 115200 Baud 8N1 (x16 clock factor, 1 stop bit, no parity, no auto-enables).
  4. Repeatedly streams `"Hello from Zx50 Serial Port A (115200 8N1)!\r\n"` with a ~0.5s pause between bursts.
* **Assemble Command:**
  ```bash
  sjasmplus --fullpath --lst=testroms/2-serial_tx_polled.lst --sld=testroms/2-serial_tx_polled.sld --sym=testroms/2-serial_tx_polled.sym testroms/2-serial_tx_polled.z80
  ```
* **Flash Command:**
  ```bash
  minipro -p SST39SF040 -w 2-serial_tx_polled.bin -s
  ```
* **Terminal Settings:** 115200 Baud, 8N1, Flow Control: None.

---

## 3. `3-serial_echo_polled.z80` (`3-serial_echo_polled.bin`, 238 bytes)
* **Goal:** Verify bidirectional serial communication (Rx and Tx) over FTDI USB.
* **Dependencies:** None (Pure polled I/O, No RAM, No Stack, No Interrupts).
* **Behavior:**
  1. Displays `"Serial Echo ON...\n"` on Front Panel LCD.
  2. Initializes CTC Ch0 and SIO ChA for 115200 8N1.
  3. Sends initial greeting prompt to the serial terminal.
  4. Enters an infinite polled loop: whenever a character is received in SIO RR0, reads it from Data Port `0x84` and echoes it back immediately.
* **Assemble Command:**
  ```bash
  sjasmplus --fullpath --lst=testroms/3-serial_echo_polled.lst --sld=testroms/3-serial_echo_polled.sld --sym=testroms/3-serial_echo_polled.sym testroms/3-serial_echo_polled.z80
  ```
* **Flash Command:**
  ```bash
  minipro -p SST39SF040 -w 3-serial_echo_polled.bin -s
  ```

---

## 4. `4-ram_mmu_test.z80` (`4-ram_mmu_test.bin`, 191 bytes)
* **Goal:** Verify the CPLD MMU mapping and physical SRAM read/write operations.
* **Dependencies:** MMU Port `0x30`, LCD Port `0x50` (Code executes from ROM at `0x0000`, testing RAM at `0x8000`).
* **Behavior:**
  1. Displays `"RAM Testing...\n"` on LCD.
  2. Uses MMU Port `0x30` to map Physical RAM Page 0 to Logical Window 8 (`0x8000 - 0x8FFF`).
  3. Fills 4KB with `0xAA` and verifies every byte.
  4. Fills 4KB with `0x55` and verifies every byte.
  5. Fills 4KB with an address pattern (low byte of address) and verifies every byte.
  6. If all patterns match, displays `"RAM TEST PASS!\n"` on LCD.
  7. If any mismatch occurs, displays `"RAM TEST FAIL!\n"` on LCD.
  8. Executes `HALT`.
* **Assemble Command:**
  ```bash
  sjasmplus --fullpath --lst=testroms/4-ram_mmu_test.lst --sld=testroms/4-ram_mmu_test.sld --sym=testroms/4-ram_mmu_test.sym testroms/4-ram_mmu_test.z80
  ```
* **Flash Command:**
  ```bash
  minipro -p SST39SF040 -w 4-ram_mmu_test.bin -s
  ```


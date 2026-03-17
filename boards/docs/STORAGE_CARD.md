# Zx50 NetStorage Card (Combo Ethernet & USB/SD)

## 1. Overview
The Zx50 NetStorage card provides the system with physical network connectivity and FAT16/FAT32 mass storage. By utilizing dual 8-bit parallel interfaces, both subsystems can achieve high-speed data transfers (and native Pi Pico DMA compatibility over the Shadow Bus) without bottlenecking the Z80.

## 2. Core Components
* **Ethernet:** **WIZnet W5300**. A high-performance hardware TCP/IP stack with a native 8-bit/16-bit parallel bus. (Configured in 8-bit mode). It features 8 independent hardware sockets and 128KB of internal TX/RX buffer memory.
* **Mass Storage:** **WCH CH376S**. A file management control chip that natively handles FAT file systems on USB flash drives and SD cards via an 8-bit parallel interface.
* **Bus Firewall:** Two `74AHCT245` transceivers for the Data bus, strictly controlled by the board's address decoder to prevent bus contention.

## 3. Addressing Strategy: Memory vs. I/O
The Z80 has two distinct addressing spaces: a 64KB Memory space and a 256-port (typically) I/O space. 

### Mass Storage (CH376S) -> I/O Mapped
* **Requirement:** The CH376S only requires **two** addresses: a Data port and a Command port.
* **Implementation:** We will map this to the standard Z80 I/O space using a `74AHCT138` decoder. For example, mapping it to I/O Ports `0x40` (Data) and `0x41` (Command). This uses almost zero real estate in the I/O map and is perfect for standard `IN A, (n)` and `OUT (n), A` instructions.

### Ethernet (W5300) -> Memory Mapped
* **Requirement:** The W5300 has a massive register set requiring **10 address lines** (`A0` through `A9`), effectively taking up 1024 bytes of address space. 
* **Implementation:** While the Z80 *can* do 16-bit I/O addressing via `IN A, (C)`, trying to cram 1KB of registers into the I/O space is messy. Instead, we will **Memory Map** the W5300. We will dedicate a 2KB or 4KB "window" in the Z80's upper memory space (e.g., `0xE000` to `0xE3FF`). 
* **Advantage:** Memory mapping allows the Z80 to use high-speed block move instructions (`LDIR`, `LDDR`) to blast data into the Ethernet transmit buffers exponentially faster than iterating through I/O ports.

## 4. Interrupts
Both chips feature active-low hardware interrupt pins (`~INT`). These will be tied into the Zx50 Backplane's open-drain `~INT` line, allowing either the Ethernet chip (e.g., "Packet Received") or the Storage chip (e.g., "File Read Complete") to flag the Z80 asynchronously.

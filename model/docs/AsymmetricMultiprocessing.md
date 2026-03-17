# Zx50 Dual-CPU Shared Memory Architecture
**Project**: Distributed AMP (Asymmetric Multiprocessing) over the Zx50 Shadow Bus
**Target**: Atmel ATF1508AS CPLD (128 Macrocells)

## 1. The Architectural Overview
The goal is to physically bridge two distinct Z80 backplanes to create a shared-memory multiprocessing system. This is achieved by linking two Zx50 Memory Cards together via the external **Shadow Bus** ribbon cable. 

Because the CPLD is entirely out of physical I/O pins (78 of ~80 pins utilized), we cannot add a dedicated bridge connector. The entire memory coherence and CPU signaling protocol must be multiplexed over the existing Shadow Bus lines (`sh_data`, `sh_stb_n`, `sh_busy_n`, `sh_en_n`, etc.).

Furthermore, because the Z80 uses physical addressing (no cache lines), we do not need to burn macrocells on complex MESI-style cache tagging. We will rely on **Wait-States, Hardware Mutexes, and Mailbox Doorbells**.

---

## 2. Feature 1: Cross-Cable Wait States (Collision Avoidance)
To prevent physical bus contention when both CPUs attempt to access the shared SRAM at the exact same time, the CPLDs will implement hardware-level stalling.

* **The Request:** CPU A initiates a read/write to the shared memory window. Card A's CPLD checks the status of the `sh_busy_n` line on the ribbon cable.
* **The Stall:** If Card B is currently executing an operation in the shared memory, it holds `sh_busy_n` low. Card A immediately asserts `z80_wait_n` on its local backplane, freezing CPU A mid-instruction.
* **The Resolution:** The nanosecond Card B finishes its cycle and releases `sh_busy_n`, Card A seizes the Shadow Bus, releases `z80_wait_n`, and allows CPU A to complete its cycle. 
* **Result:** Zero bus crashes. Neither CPU is aware the other exists; they simply experience a few nanoseconds of invisible latency.

---

## 3. Feature 2: Hardware Mutex / Spinlock (Test-and-Set)
While Wait-States prevent electrical collisions, they do not prevent software race conditions (e.g., CPU A and CPU B both trying to modify the same linked list simultaneously). We will implement a hardware lock using just a few macrocells.

* **The Implementation:** A 1-bit register inside the CPLD mapped to a specific I/O port (e.g., `0x50`).
* **Atomic Read-and-Set:** When a CPU *reads* port `0x50`, the CPLD outputs the current state of the lock (0 = Unlocked, 1 = Locked) to the data bus. In the exact same physical clock cycle, the CPLD forces the lock to `1`. 
* **The Software Spin:** * If CPU A reads `0`, it knows it has safely acquired the lock and can modify the shared memory. 
  * If CPU B reads the port a microsecond later, it receives a `1` and enters a software loop (spinning) until it reads a `0`.
* **The Release:** When CPU A is finished with the shared resource, it simply *writes* `0` to port `0x50`, releasing the lock for CPU B.

---

## 4. Feature 3: Mailboxes / Inter-Processor Interrupts (Doorbells)
To prevent the CPUs from wasting cycles constantly polling the shared memory for new data, we will implement an asynchronous "Doorbell" system.

* **The Trigger:** CPU A wants to send a message to CPU B. It places the data in shared memory, then writes to a specific "Mailbox" I/O port on its local CPLD.
* **The Shadow Strobe:** Card A's CPLD translates this I/O write into a specific sequence or strobe over the shared Shadow Bus lines (e.g., pulling a specific control line low while the data bus is idle).
* **The Interrupt:** Card B detects this specific strobe condition on the ribbon cable and immediately pulls the `z80_int_n` line low on its local backplane.
* **The Handler:** CPU B jumps to its Interrupt Service Routine (ISR), reads the mailbox flag, and processes the new data CPU A left in the shared memory.

---

## Summary of Resource Utilization
* **Physical Pins Required:** 0 (Multiplexed over existing Shadow Bus)
* **Macrocells Required:** Estimated ~10-15 (Well within the ~110 remaining limit of the ATF1508AS)
* **Software Overhead:** Minimal (Managed entirely via native Z80 `IN`, `OUT`, and standard Interrupts)
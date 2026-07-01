# Zx50 Operating System: Interrupt-Driven Serial I/O Architecture

This document outlines the architectural plan for transitioning the Zx50 OS from a blocking, polled serial I/O model to a fully interrupt-driven, non-blocking asynchronous model. This design supports dual independent serial ports (Port A and Port B) and abstracts the hardware from user-space applications using memory-based ring buffers.

---

## 1. Core Concepts

* **Asynchronous Execution:** Applications will interact exclusively with memory buffers rather than directly polling hardware registers. This allows the CPU to process data while serial transmission occurs in the background.
* **Dual Port Support:** SIO Port A (Console) and SIO Port B (Debug/Aux) will operate completely independently, each backed by its own dedicated transmit (Tx) and receive (Rx) buffers.
* **Vector Routing:** The Z80 SIO's "Status Affects Vector" feature will be enabled, allowing the hardware to automatically route interrupts to specific, highly-optimized Interrupt Service Routines (ISRs) for Tx and Rx events on both ports.

---

## 2. The Lock-Free Ring Buffer (`ring_buffer.z80`)

To encapsulate memory management, we define a reusable, thread-safe `STRUCT`. 

By strictly adhering to a Single-Producer / Single-Consumer (SPSC) contract and dropping the `Count` variable, the buffer is entirely **lock-free**. The Producer exclusively modifies `Head`, and the Consumer exclusively modifies `Tail`. This allows the ISR and the OS to operate concurrently without `DI`/`EI` wrapping around the core pointer math.

### Structure Definition
```assembly
    ; Defined in defines.z80
    RB_SIZE     EQU 64             ; MUST be a power of 2!
    RB_MASK     EQU RB_SIZE - 1    ; e.g., 0x3F

    ; Defined in ring_buffer.z80
    STRUCT RingBuffer
        Head    BYTE    ; Write index (Modified ONLY by Producer)
        Tail    BYTE    ; Read index  (Modified ONLY by Consumer)
        Data    BLOCK RB_SIZE
    ENDS
```

### Memory Allocation
The OS RAM will reserve space for four distinct queues using this blueprint: `PortA_Rx_RB`, `PortA_Tx_RB`, `PortB_Rx_RB`, and `PortB_Tx_RB`.

---

## 3. The Ring Buffer API

The `ring_buffer.z80` module exposes a standard API. The caller must load the `IX` register with a pointer to the target `RingBuffer` instance.

* **`RB_Init`**: Resets `Head` and `Tail` to `0`.
* **`RB_Write` (Producer)**: Calculates `NextHead`. If it matches `Tail`, sets the Carry Flag (Buffer Full). Otherwise, writes the byte, publishes the new `Head`, and clears the Carry Flag.
* **`RB_Read` (Consumer)**: Compares `Head` to `Tail`. If they match, sets the Carry Flag (Buffer Empty). Otherwise, reads the byte, publishes the new `Tail`, and clears the Carry Flag.

### Blocking Helpers & The "Lost Wakeup" Fix
To allow applications to easily wait for data, we provide blocking wrappers. To prevent the "Lost Wakeup" race condition (where an interrupt fires between the empty-check and the CPU going to sleep), we leverage the Z80's native 1-instruction `EI` delay:

```assembly
RB_Blocking_Read:
.wait_loop:
    DI                              ; 1. Disable interrupts to prevent race condition
    CALL RB_Read
    JR C, .buffer_empty             ; 2. If Carry is SET, buffer is empty
    EI                              ; 3. Read succeeded! Re-enable interrupts and return.
    RET
.buffer_empty:
    EI                              ; 4. Re-enable interrupts... but delayed by 1 instruction!
    HALT                            ; 5. CPU sleeps safely. Any pending INT fires right AFTER this.
    JR .wait_loop                   ; 6. Wake up and try reading again.
```

---

## 4. Hardware Interrupt Logic

### Receive (Rx) ISR - "Interrupt on First Character"
1. The Rx ISR executes a fast loop, reading the SIO data port.
2. It passes the target buffer (e.g., `PortA_Rx_RB`) to `RB_Write`.
3. Continues looping until the SIO's "Rx Character Available" status bit drops, then exits.

### Transmit (Tx) ISR - "Transmit Buffer Empty"
1. The Tx ISR calls `RB_Read` on the target buffer.
2. If a byte is retrieved, it writes it to the SIO data port and exits.
3. **Crucial State Management:** If `RB_Read` returns empty (Carry Flag set), the Tx ISR **MUST** disable the SIO's Tx Interrupt to prevent an infinite interrupt loop lockup.

---

## 5. Line Disciplines (Raw vs. Cooked Mode)

The OS will maintain a global "Line Discipline" state for each port.
* **Cooked Mode (Default):** The Rx ISR actively inspects incoming bytes before enqueuing them. Special characters like `0x03` (Ctrl+C) are trapped and routed to the OS process manager to abort the current application.
* **Raw Mode:** Enabled via an OS Syscall. The Rx ISR bypasses all inspection and blindly enqueues every byte exactly as received from the wire, allowing safe XMODEM/binary transfers.

---

## 6. System Call Abstraction

User applications will no longer use `IN` or `OUT` instructions. They will interact solely with the OS via updated System Calls:
* **`Sys_ReadChar`:** Polls `RB_Blocking_Read` on the Rx buffer. 
* **`Sys_PrintChar`:** Polls `RB_Blocking_Write` on the Tx buffer. Once successfully written, it manually re-enables the SIO Tx Interrupt to kickstart the hardware serialization process.
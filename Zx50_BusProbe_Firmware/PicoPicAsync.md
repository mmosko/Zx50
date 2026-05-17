# Zx50 Bus Probe: Asynchronous Protocol & State Machine

## 1. Architectural Overview

The Zx50 Bus Probe originally utilized a synchronous Remote Procedure Call (RPC) paradigm. The Pico (Host) would send a command (e.g., Memory Read) and block until the PIC18 completed the full Z80 instruction cycle (T1, T2, T3) and returned the result.

While this worked for auto-running clocks, it fundamentally broke **Manual Stepping Mode**. If the user wanted to step the clock manually via the front panel `AUX` switch to observe the bus states, the PIC would pause mid-instruction. This caused the Pico's UART timeout to expire, dropping the packet and breaking the CLI.

To resolve this, the protocol has been redesigned as a **Fully Asynchronous Polling System**.
1. **Submission:** The Pico submits a command and receives an immediate `RESP_QUEUED` acknowledgment.
2. **Execution:** The PIC processes the command asynchronously (either driven by the 1kHz auto-clock timer or manual `AUX` steps).
3. **Retrieval:** The Pico polls the PIC (via `CMD_STEP` or `CMD_STATUS`) to check if the command is complete and fetch the data payload.

---

## 2. Protocol Definitions

### 2.1 Command Opcodes (Pico $\rightarrow$ PIC)
* `CMD_LD (0x01)`: Queue Memory Read.
* `CMD_STORE (0x02)`: Queue Memory Write.
* `CMD_IN (0x03)`: Queue I/O Read.
* `CMD_OUT (0x04)`: Queue I/O Write.
* `CMD_STEP (0x11)`: Advance the clock 1 cycle (if auto-clock is off) and return queue status.
* `CMD_STATUS (0x15)`: *[NEW]* Return queue status without advancing the clock.

### 2.2 Response Codes (PIC $\rightarrow$ Pico)
* `RESP_QUEUED (0x5C)`: Command accepted into the empty queue slot.
* `RESP_PENDING (0x5D)`: Command is actively executing (currently in T1 or T2).
* `RESP_DONE (0x5E)`: Command finished (T cycle completed). A data byte immediately follows if the command was a Read.
* `RESP_IDLE (0x5F)`: Queue is empty. Nothing is executing.
* `SYNC_OK (0x5A)`: Command accepted (e.g. non-queued commend, like STEP).
* `SYNC_NACK (0x5B)`: Command rejected (e.g., Queue is full or invalid syntax).

---

## 3. State Machines

### 3.1 PIC18 State Machine (Command Queue)

The PIC maintains a command queue and tracks the Z80 T-States for the active command.

```plantuml
@startuml
skinparam handwritten false
skinparam shadowing false
skinparam state {
  BackgroundColor White
  BorderColor Black
  ArrowColor Black
}

[*] --> STAT_EMPTY

STAT_EMPTY --> STAT_PENDING : Rx Bus Command\n(Tx RESP_QUEUED)
STAT_PENDING --> STAT_PROCESSING : Clock Pulses\nEnter T1
STAT_PROCESSING --> STAT_PROCESSING : Clock Pulses\nEnter T2 (Wait States)
STAT_PROCESSING --> STAT_DONE : Clock Pulses\nEnter T cycle (Data Latched)
STAT_DONE --> STAT_EMPTY : Rx CMD_STATUS or CMD_STEP\n(Tx RESP_DONE + Data)

@enduml
```

**State Definitions:**

* `STAT_EMPTY`: No command loaded. If stepped or polled, returns `RESP_IDLE`.
* `STAT_PENDING`: Command is queued but hasn't started its T1 cycle yet.
* `STAT_PROCESSING`: The PIC is actively driving the transceivers and holding the bus.
* `STAT_DONE`: The Z80 cycle is complete. The result is buffered. The PIC waits for the Pico to retrieve it, then clears the queue.


### 3.2 Pico State Machine (Host CLI)

The Pico CLI must track whether it is waiting for a bus operation to complete, preventing the user from overflowing the queue.

```plantuml
@startuml
skinparam handwritten false
skinparam shadowing false
skinparam state {
  BackgroundColor White
  BorderColor Black
  ArrowColor Black
}

[*] --> HOST_IDLE

HOST_IDLE --> HOST_WAITING : Send CMD_LD / CMD_STORE\n(Rx RESP_QUEUED)
HOST_WAITING --> HOST_WAITING : Send CMD_STEP / CMD_STATUS\n(Rx RESP_PENDING)
HOST_WAITING --> HOST_IDLE : Send CMD_STEP / CMD_STATUS\n(Rx RESP_DONE)

@enduml
```

**State Definitions:**

* `HOST_IDLE`: Ready to accept new CLI commands.
* `HOST_WAITING`: A bus command is queued. New bus commands are rejected locally. The user must issue `pic step` or `pic status` to resolve the pending command.

---

## 4. Sequence Diagrams

### 4.1 Scenario A: Manual Stepping (Read Operation)

This scenario demonstrates how the asynchronous protocol allows the user to manually step through a Memory Read without triggering a UART timeout on the Pico.

```plantuml
@startuml
skinparam maxMessageSize 150
participant Pico
participant PIC18
participant Z80_Bus

== Submission Phase ==
Pico -> PIC18 : CMD_LD 0x1234
PIC18 -> Pico : RESP_QUEUED
note over Pico : State: HOST_WAITING

== Execution Phase (Manual Steps) ==
Pico -> PIC18 : CMD_STEP
PIC18 -> Z80_Bus : Execute T1 (Address Out)
PIC18 -> Pico : RESP_PENDING

Pico -> PIC18 : CMD_STEP
PIC18 -> Z80_Bus : Execute T2 (~RD Falls)
PIC18 -> Pico : RESP_PENDING

Pico -> PIC18 : CMD_STEP
PIC18 -> Z80_Bus : Execute T cycle (Latch Data)
PIC18 -> Pico : RESP_DONE [0x42]

== Retrieval Phase ==
note over Pico : State: HOST_IDLE\nPrints: "OK 42"
@enduml

```

### 4.2 Scenario B: Auto-Clock Mode (Write Operation)

When the 1kHz auto-clock is running, the PIC will execute the command in the background immediately. The Pico uses `CMD_STATUS` to poll for completion.

```plantuml
@startuml
participant Pico
participant PIC18
participant Z80_Bus

Pico -> PIC18 : CMD_CLK_START
PIC18 -> Pico : ACK

== Submission Phase ==
Pico -> PIC18 : CMD_STORE 0x1234 0xFF
PIC18 -> Pico : RESP_QUEUED
note over Pico : State: HOST_WAITING

== Background Execution ==
note over PIC18 : Timer ISR fires 3x (3ms)
PIC18 -> Z80_Bus : T1, T2, T3, T4 execute automatically
note over PIC18 : State moves to STAT_DONE

== Polling Phase ==
Pico -> PIC18 : CMD_STATUS
PIC18 -> Pico : RESP_DONE
note over Pico : State: HOST_IDLE\nPrints: "OK"
@enduml

```

### 4.3 Scenario C: Hardware AUX Switch Stepping

If the user steps the clock using the physical hardware switch on the PCB instead of the CLI, the PIC completes the command silently. The Pico retrieves it via `CMD_STATUS`.

```plantuml
@startuml
participant Pico
participant PIC18
actor User

Pico -> PIC18 : CMD_LD 0x1000
PIC18 -> Pico : RESP_QUEUED

User -> PIC18 : Toggle AUX Switch
note over PIC18 : Executes T1
User -> PIC18 : Toggle AUX Switch
note over PIC18 : Executes T2
User -> PIC18 : Toggle AUX Switch
note over PIC18 : Executes T3 (Done)

Pico -> PIC18 : CMD_STATUS
PIC18 -> Pico : RESP_DONE [0xAA]
@enduml
```

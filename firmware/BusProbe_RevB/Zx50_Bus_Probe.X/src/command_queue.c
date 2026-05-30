#include <stdbool.h>
#include "command_queue.h"
#include "clock.h"
#include "hal.h"
#include "z80_bus.h"
#include "wait.h"

typedef enum {
    OP_IDLE = 0,
    OP_MEM_READ,
    OP_MEM_WRITE,
    OP_IO_READ,
    OP_IO_WRITE
} bus_op_t;

typedef struct {
    bus_op_t op;
    uint16_t address;
    uint8_t  data_in;
    uint8_t  data_out;
    volatile cmd_status_t status;
} cmd_t;

#define QUEUE_SIZE 8
static cmd_t command_queue[QUEUE_SIZE];
static uint8_t head = 0;
static uint8_t tail = 0;

static t_cycle_t current_t_state = CYCLE_T1;

// --- Private Enqueue Helper ---
static inline bool _CQ_Enqueue(bus_op_t op, uint16_t address, uint8_t data) {
    uint8_t next_tail = (tail + 1) % QUEUE_SIZE;
    if (next_tail == head) return false; // Queue Full

    command_queue[tail].op = op;
    command_queue[tail].address = address;
    command_queue[tail].data_in = data;
    command_queue[tail].status = STAT_PENDING;

    tail = next_tail;
    return true;
}

// --- Public API ---
bool CQ_Enqueue_MemRead(uint16_t address) { return _CQ_Enqueue(OP_MEM_READ, address, 0); }
bool CQ_Enqueue_MemWrite(uint16_t address, uint8_t data) { return _CQ_Enqueue(OP_MEM_WRITE, address, data); }
bool CQ_Enqueue_IoRead(uint16_t address) { return _CQ_Enqueue(OP_IO_READ, address, 0); }
bool CQ_Enqueue_IoWrite(uint16_t address, uint8_t data) { return _CQ_Enqueue(OP_IO_WRITE, address, data); }

cmd_status_t CQ_Get_Head_Status(void) { return command_queue[head].status; }

void CQ_Init(void) {
    head = 0;
    tail = 0;
    current_t_state = CYCLE_T1;
    for (int i = 0; i < QUEUE_SIZE; i++) {
        command_queue[i].status = STAT_EMPTY;
        command_queue[i].op = OP_IDLE;
    }
}

bool CQ_Read_Head_Data(uint8_t *data) {
    if (command_queue[head].status == STAT_DONE) {
        if (command_queue[head].op == OP_MEM_READ || command_queue[head].op == OP_IO_READ) {
            *data = command_queue[head].data_out;
            return true;
        }
    }
    return false;
}

void CQ_Pop_Head(void) {
    command_queue[head].status = STAT_EMPTY;
    command_queue[head].op = OP_IDLE;
    head = (head + 1) % QUEUE_SIZE;
}

// --- State Machine Logic ---
static inline void CQ_AdvanceTState() {
    switch (current_t_state) {
        case CYCLE_T1:
            current_t_state = CYCLE_T2;
            break;

        case CYCLE_T2:
            #ifndef IN_SIMULATOR
            // 1. If PIC is an input, and line is low -> Target is waiting
            if (Z80_WAIT_DIR == 1 && Z80_WAIT_VAL == 0) {
                break;
            }
            // 2. If PIC is an output floating high (Open-Drain), but line is low -> Target is waiting
            if (Z80_WAIT_DIR == 0 && Z80_WAIT_LAT == 1 && Z80_WAIT_VAL == 0) {
                break;
            }
            #endif

            // Otherwise, advance safely
            current_t_state = CYCLE_T3;
            break;

        case CYCLE_T3:
            current_t_state = CYCLE_T4;
            break;

        case CYCLE_T4:
            current_t_state = CYCLE_T1;
            break;
    }
}

static inline void CQ_ProcessCommand(cmd_t *cmd) {
    switch(cmd->op) {
        case OP_IDLE:
            Z80_Generate_Single_Pulse();
            break;

        case OP_MEM_WRITE:
            Z80_Mem_Write(cmd->address, cmd->data_in, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        case OP_MEM_READ:
            cmd->data_out = Z80_Mem_Read(cmd->address, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        case OP_IO_WRITE:
            Z80_IO_Write(cmd->address, cmd->data_in, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        case OP_IO_READ:
            cmd->data_out = Z80_IO_Read(cmd->address, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;
    }
}

void CQ_Dispatch_Cycle(void) {
    if (command_queue[head].status == STAT_EMPTY || command_queue[head].status == STAT_DONE) {
        // Keep the clock alive when idle!
        Z80_Generate_Single_Pulse();
        current_t_state = CYCLE_T1;
        return;
    }

    cmd_t *cmd = &command_queue[head];

    if (current_t_state == CYCLE_T1) {
        cmd->status = STAT_PROCESSING;
    }

    if (cmd->status == STAT_PROCESSING) {
        CQ_ProcessCommand(cmd);
    }
}
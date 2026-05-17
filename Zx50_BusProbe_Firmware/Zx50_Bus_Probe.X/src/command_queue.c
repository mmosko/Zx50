#include <stdbool.h>
#include "command_queue.h"
#include "clock.h"
#include "pins.h"
#include "hal.h"
#include "z80_bus.h"

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
    uint8_t  data_in;   // Data to write to the bus
    uint8_t  data_out;  // Data read from the bus
    volatile cmd_status_t status; // Volatile because it is modified by the ISR
} cmd_t;


#define QUEUE_SIZE 8
static cmd_t enqueue[QUEUE_SIZE];
static uint8_t head = 0;
static uint8_t tail = 0;

static t_cycle_t current_t_state = CYCLE_T1; 

// --- NEW API IMPLEMENTATION ---

// --- PRIVATE ENQUEUE HELPER ---
static inline bool _CQ_Enqueue(bus_op_t op, uint16_t address, uint8_t data) {
    uint8_t next_tail = (tail + 1) % QUEUE_SIZE;
    if (next_tail == head) return false; // Queue Full!
    
    enqueue[tail].op = op;
    enqueue[tail].address = address;
    enqueue[tail].data_in = data;
    enqueue[tail].status = STAT_PENDING; 
    
    tail = next_tail;
    return true; 
}

// --- PUBLIC ENQUEUE API ---
bool CQ_Enqueue_MemRead(uint16_t address) {
    return _CQ_Enqueue(OP_MEM_READ, address, 0);
}

bool CQ_Enqueue_MemWrite(uint16_t address, uint8_t data) {
    return _CQ_Enqueue(OP_MEM_WRITE, address, data);
}

bool CQ_Enqueue_IoRead(uint16_t address) {
    return _CQ_Enqueue(OP_IO_READ, address, 0);
}

bool CQ_Enqueue_IoWrite(uint16_t address, uint8_t data) {
    return _CQ_Enqueue(OP_IO_WRITE, address, data);
}
// --------------------------

cmd_status_t CQ_Get_Head_Status(void) {
    return enqueue[head].status;
}

bool CQ_Read_Head_Data(uint8_t *data) {
    if (enqueue[head].status == STAT_DONE) {
        // Only valid for read operations
        if (enqueue[head].op == OP_MEM_READ || enqueue[head].op == OP_IO_READ) {
            *data = enqueue[head].data_out;
            return true;
        }
    }
    return false; // Not done, or not a read operation
}

void CQ_Pop_Head(void) {
    enqueue[head].status = STAT_EMPTY;
    enqueue[head].op = OP_IDLE;
    head = (head + 1) % QUEUE_SIZE;
}
// ------------------------------

static inline
void CQ_AdvanceTState() {
    switch (current_t_state) {
        case CYCLE_T1:
            current_t_state = CYCLE_T2;
            break;
        case CYCLE_T2:           
            #ifndef IN_SIMULATOR
            if (Z80_WAIT_DIR == 1 && Z80_WAIT_VAL == 0) break;
            if (Z80_WAIT_DIR == 0 && Z80_WAIT_LAT == 1)
                if (Z80_WAIT_VAL == 0) break;
            #endif
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

static inline
void CQ_ProcessCommand(cmd_t *cmd) {
    switch(cmd->op) {
        case OP_IDLE:
            Z80_Clock_Pulse();
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
    if (enqueue[head].status == STAT_EMPTY || enqueue[head].status == STAT_DONE) {
        Z80_Clock_Pulse();
        current_t_state = CYCLE_T1;
        return;
    }

    cmd_t *cmd = &enqueue[head];

    if (current_t_state == CYCLE_T1) {
        cmd->status = STAT_PROCESSING;
    }

    if (cmd->status == STAT_PROCESSING) {
        CQ_ProcessCommand(cmd);
    }
}

#include "command_queue.h"
#include "clock.h"
#include "pins.h"
#include "hal.h"
#include "z80_bus.h"

#define QUEUE_SIZE 8
static cmd_t enqueue[QUEUE_SIZE];
static uint8_t head = 0;
static uint8_t tail = 0;

// Tracks which T-State (1, 2, or 3) the current command is executing
static t_cycle_t current_t_state = CYCLE_T1; 

cmd_t* CQ_Enqueue(bus_op_t op, uint16_t address, uint8_t data) {
    uint8_t next_tail = (tail + 1) % QUEUE_SIZE;
    if (next_tail == head) return 0; // Queue Full!
    
    enqueue[tail].op = op;
    enqueue[tail].address = address;
    enqueue[tail].data_in = data;
    enqueue[tail].status = STAT_PENDING; // Mark ready for the ISR
    
    cmd_t* cmd_ptr = &enqueue[tail];
    tail = next_tail;
    return cmd_ptr;
}

void CQ_Clear(cmd_t *cmd) {
    cmd->status = STAT_EMPTY;
    cmd->op = OP_IDLE;
    cmd->address = 0;
    cmd->data_in = 0;
    cmd->data_out = 0;
}


static inline
void CQ_AdvanceHead() {
    head = (head + 1) % QUEUE_SIZE;
}

static inline
void CQ_AdvanceTState() {
    switch (current_t_state) {
        case CYCLE_T1:
            current_t_state = CYCLE_T2;
            break;
        case CYCLE_T2:           
            #ifndef IN_SIMULATOR
            // We are reading WAIT and it is asserted
            if (Z80_WAIT_DIR == 1 && Z80_WAIT_VAL == 0) {
                break;
            }
            
            if (Z80_WAIT_DIR == 0 && Z80_WAIT_LAT == 1)
                if (Z80_WAIT_VAL == 0) {
                    // we do not advance out of T2
                    break;
                }
            #endif
            current_t_state = CYCLE_T3;
            break;
        case CYCLE_T3:
            // most things do not have a T4, so it will be a no-op and
            // not advance the clock
            current_t_state = CYCLE_T4;
            break;
        case CYCLE_T4:
            // most things do not have a T4, so it will be a no-op and
            // not advance the clock
            current_t_state = CYCLE_T1;
            break;
    }
}

static inline
void CQ_ProcessCommand(cmd_t *cmd) {
    // 3. The T-State Dispatcher (State Machine)
    switch(cmd->op) {
        case OP_IDLE:
            // I don't think these ever get executed here, but just in case
            // we pulse the clock
            Z80_Clock_Pulse();
            break;
            
        // -----------------------------------------------------
        // MEMORY WRITE
        // -----------------------------------------------------
        case OP_MEM_WRITE:
            Z80_Mem_Write(cmd->address, cmd->data_in, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                CQ_AdvanceHead();
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        // -----------------------------------------------------
        // MEMORY READ
        // -----------------------------------------------------
        case OP_MEM_READ:
            // data_out will only be valid on T3
            cmd->data_out = Z80_Mem_Read(cmd->address, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                CQ_AdvanceHead();
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        // -----------------------------------------------------
        // IO WRITE
        // -----------------------------------------------------
        case OP_IO_WRITE:
            Z80_IO_Write(cmd->address, cmd->data_in, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                CQ_AdvanceHead();
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;

        // -----------------------------------------------------
        // IO READ
        // -----------------------------------------------------
        case OP_IO_READ:
            // data_out will only be valid on T3
            cmd->data_out = Z80_IO_Read(cmd->address, current_t_state);
            if (current_t_state == CYCLE_T3) {
                cmd->status = STAT_DONE;
                CQ_AdvanceHead();
                current_t_state = CYCLE_T1;
            } else {
                CQ_AdvanceTState();
            }
            break;            
    }
}


void CQ_Dispatch_Cycle(void) {
    // 1. If queue is empty or the command is finished, just pulse an idle clock
    if (enqueue[head].status == STAT_EMPTY || enqueue[head].status == STAT_DONE) {
        Z80_Clock_Pulse();
        // this is the "idle" state
        current_t_state = CYCLE_T1;
        return;
    }

    // If this is called from the ISR, the PIC has already masked interrupts
    // until we return.
    
    // The same command stays at the head of the queue until it finishes
    // its T states.
    cmd_t *cmd = &enqueue[head];

    // 2. Start Processing a new command
    if (current_t_state == CYCLE_T1) {
        cmd->status = STAT_PROCESSING;
    }

    // Run through all the clock cycles fast for a single command
    while (cmd->status == STAT_PROCESSING) {
        CQ_ProcessCommand(cmd);
    }
}


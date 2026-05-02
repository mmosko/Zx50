/*
 * File:   command_queue.h
 * Description: Interrupt-safe Z80 Bus Operation Queue
 */

#ifndef COMMAND_QUEUE_H
#define COMMAND_QUEUE_H

#include <stdint.h>

typedef enum {
    OP_IDLE = 0,
    OP_MEM_READ,
    OP_MEM_WRITE,
    OP_IO_READ,
    OP_IO_WRITE
} bus_op_t;

typedef enum {
    STAT_EMPTY = 0,
    STAT_PENDING,
    STAT_PROCESSING,
    STAT_DONE
} cmd_status_t;

typedef struct {
    bus_op_t op;
    uint16_t address;
    uint8_t  data_in;   // Data to write to the bus
    uint8_t  data_out;  // Data read from the bus
    volatile cmd_status_t status; // Volatile because it is modified by the ISR
} cmd_t;

// Face 1: Called by main.c to schedule a job
cmd_t* CQ_Enqueue(bus_op_t op, uint16_t address, uint8_t data);

// Face 2: Called by the ISR/Single-Step to execute exactly ONE clock cycle
void CQ_Dispatch_Cycle(void);

// clears the command state so it can be recycled
void CQ_Clear(cmd_t *cmd);

#endif /* COMMAND_QUEUE_H */
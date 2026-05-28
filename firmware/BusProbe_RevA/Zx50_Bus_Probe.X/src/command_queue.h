/*
 * File:   command_queue.h
 * Description: Interrupt-safe Z80 Bus Operation Queue
 */

#ifndef COMMAND_QUEUE_H
#define COMMAND_QUEUE_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    STAT_EMPTY = 0,
    STAT_PENDING,
    STAT_PROCESSING,
    STAT_DONE
} cmd_status_t;

// ==== ENQUEUE API ====

// Called by main.c to schedule a job.  Returns TRUE if the
// command is enqueues, false if it cannot be queues (i.e. the queue is full).)

bool CQ_Enqueue_MemRead(uint16_t address);
bool CQ_Enqueue_MemWrite(uint16_t address, uint8_t data);
bool CQ_Enqueue_IoRead(uint16_t address);
bool CQ_Enqueue_IoWrite(uint16_t address, uint8_t data);

// =====================

// Called by the ISR/Single-Step to execute exactly ONE clock cycle
void CQ_Dispatch_Cycle(void);

cmd_status_t CQ_Get_Head_Status(void);

// If the head element returns data and it has data available, it
// will put that data in the data pointer and return "true".  If
// "false" is returned, data is unmodified.
// Should only be used with STAT_DONE.
bool CQ_Read_Head_Data(uint8_t *data);

// Removes the head element.  Typically, this is used by main to
// clear the head element after it has processed the STAT_DONE and
// optionally read any return data.
void CQ_Pop_Head(void);

#endif /* COMMAND_QUEUE_H */
/* 
 * File:   cmd.h
 * Author: marc
 *
 * Created on May 16, 2026, 9:18 PM
 */

#ifndef CMD_H
#define CMD_H

// ==========================================
// Packet Opcodes (Pico -> PIC)
// ==========================================
#define CMD_LD             0x01
#define CMD_STORE          0x02
#define CMD_IN             0x03
#define CMD_OUT            0x04
#define CMD_LDIR           0x05
#define CMD_SNAPSHOT       0x07  
#define CMD_GHOST          0x08
#define CMD_STEP           0x11  
#define CMD_BOOT           0x14
#define CMD_STATUS         0x15

// Simplified Clock Commands
#define CMD_CLK_AUTO       0x20
#define CMD_CLK_SYNC       0x21
#define CMD_CLK_OFF        0x22

// ==========================================
// Async Response Codes (PIC -> Pico)
// ==========================================
#define SYNC_OK            0x5A
#define SYNC_NACK          0x5B
#define RESP_QUEUED        0x5C
#define RESP_PENDING       0x5D
#define RESP_DONE          0x5E
#define RESP_IDLE          0x5F

#endif /* CMD_H */
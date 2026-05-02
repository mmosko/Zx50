/*
 * File:   main.c
 * Author: Marc Mosko
 */

// ==========================================
// PIC18F4620 Configuration Bits (Fuses)
// ==========================================
#pragma config OSC = INTIO67    // Oscillator Selection: Internal oscillator, RA6/RA7 are digital I/O
#pragma config FCMEN = OFF      // Fail-Safe Clock Monitor: Disabled
#pragma config IESO = OFF       // Internal/External Osc Switchover: Disabled
#pragma config PWRT = ON        // Power-up Timer: Enabled (Wait for power to stabilize)
#pragma config BOREN = SBORDIS  // Brown-out Reset: Hardware only
#pragma config BORV = 3         // Brown-out Reset Voltage: Minimum setting
#pragma config WDT = OFF        // Watchdog Timer: Disabled (CRITICAL!)
#pragma config MCLRE = ON       // MCLR Pin Enable: MCLR pin enabled, RE3 disabled
#pragma config PBADEN = OFF     // PORTB A/D Enable: PORTB<4:0> are digital I/O on Reset
#pragma config LVP = OFF        // Low Voltage ICSP: Disabled (CRITICAL for standard JTAG/ICSP)
#pragma config XINST = OFF      // Extended Instruction Set: Disabled (Legacy mode)

// Define the system clock frequency for the __delay_us() macro
#define _XTAL_FREQ 32000000 

#include <xc.h>
#include "hal.h"        // Adds UART_Read, System_Init, etc.
#include "z80_bus.h"
#include "clock.h"      // Included so we can pump the clock
#include "pins.h"
#include "command_queue.h"       // Included so we can release RESET

// ==========================================
// Packet Opcodes
// ==========================================
#define CMD_LD             0x01
#define CMD_STORE          0x02
#define CMD_IN             0x03
#define CMD_OUT            0x04
#define CMD_LDIR           0x05
#define CMD_SNAPSHOT       0x07  // Read state of the entire bus
#define CMD_GHOST          0x08  // 1 = Ghost (Release Bus), 0 = Unghost (Drive Bus)
#define CMD_STEP           0x11  // Clock control
#define CMD_CLK_AUTO_START 0x12  // Start 1kHz background clock
#define CMD_CLK_AUTO_STOP  0x13  // Stop 1kHz background clock

#define CMD_ACK            0x5A
#define CMD_NACK           0x5B

void main(void) {
    cmd_t *pending_cmd = 0;
    
    // Initialize pins safely to High-Z
    System_Init(); 

    // Safely reset the CPLD via the Z80 bus
    Z80_Boot_Sequence();

    uint8_t sync, opcode, addr_h, addr_l, param;

    while(1) {
        
        if (pending_cmd != NULL && pending_cmd->status == STAT_DONE) {
            switch(pending_cmd->op) {
                case OP_IDLE:
                case OP_MEM_WRITE:
                case OP_IO_WRITE:
                    // no further action needed for these
                    break;
                case OP_MEM_READ:
                    UART_Write(pending_cmd->data_out);
                    break;
                case OP_IO_READ:
                    UART_Write(pending_cmd->data_out);
                    break;
            }
            
            CQ_Clear(pending_cmd);
            pending_cmd = 0;
            continue;
        }
        
        if (!UART_Data_Available()) {
            continue;
        }
        
        // Ensure UART_Read() is non-blocking here, or check UART_Data_Available()
        // before calling UART_Read() so we don't stall the Z80_Clock_Service().
        sync = UART_Read();
        if (sync != CMD_ACK) continue; 

        // If we get a sync byte, read the rest of the 5-byte packet
        opcode = UART_Read();
        addr_h = UART_Read();
        addr_l = UART_Read();
        param  = UART_Read(); 

        uint16_t address = (((uint16_t) addr_h) << 8) | addr_l;

        switch(opcode) {
            case CMD_LD: {
                if (pending_cmd != 0) {
                    UART_Write(CMD_NACK); 
                } else {
                    pending_cmd = CQ_Enqueue(OP_MEM_READ, address, 0);
                    UART_Write(CMD_ACK);     
                }
                
                break;
            }
            case CMD_STORE: {
                if (pending_cmd != 0) {
                    UART_Write(CMD_NACK); 
                } else {
                    pending_cmd = CQ_Enqueue(OP_MEM_WRITE, address, param);
                    UART_Write(CMD_ACK);     
                }
                break;
            }
            case CMD_IN: {
                if (pending_cmd != 0) {
                    UART_Write(CMD_NACK); 
                } else {
                    pending_cmd = CQ_Enqueue(OP_IO_READ, address, 0);
                    UART_Write(CMD_ACK);     
                }
                break;
            }
            case CMD_OUT: {
                if (pending_cmd != 0) {
                    UART_Write(CMD_NACK); 
                } else {
                    pending_cmd = CQ_Enqueue(OP_IO_WRITE, address, param);
                    UART_Write(CMD_ACK);     
                }
                break;
            }
            case CMD_GHOST: {
                Ghost(param);
                UART_Write(CMD_ACK);       
                break;
            }
            case CMD_SNAPSHOT: {
                Z80_Bus_Snapshot(); 
                break;
            }
            case CMD_LDIR: {
                // not supported under async setup yet
                UART_Write(CMD_NACK);     
                break;
            }
            case CMD_STEP: {
                // always step at least once, even if user did not provide count
                if (param == 0) {
                    param = 1;
                }
                
                for (int i = 0; i < param; i++) {
                    // step clock and dispatch commands
                    CQ_Dispatch_Cycle(); 
                }
                UART_Write(CMD_ACK);     
                break;
            }
            case CMD_CLK_AUTO_START: {
                Z80_Clock_Start_Auto();
                UART_Write(CMD_ACK);     
                break;
            }
            case CMD_CLK_AUTO_STOP: {
                Z80_Clock_Stop_Auto();
                UART_Write(CMD_ACK);     
                break;
            }
            default:
                break;
        }
    }
}
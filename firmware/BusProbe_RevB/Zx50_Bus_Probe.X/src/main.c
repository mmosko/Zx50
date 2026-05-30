/*
 * File:   main.c
 * Author: Marc Mosko
 *
 * Description: Main application for the Zx50 Bus Probe Rev B.
 */

// =========================================================================
// PIC18F27Q43 Configuration Bits
// =========================================================================
#pragma config FEXTOSC = OFF    // External Oscillator not used
#pragma config RSTOSC = HFINTOSC_64MHZ // Power-on default is 64MHz internal osc
#pragma config CLKOUTEN = OFF   // CLKOUT function is disabled
#pragma config CSWEN = ON       // Allow runtime clock switching
#pragma config FCMEN = ON       // Enable Fail-Safe Clock Monitor
#pragma config MCLRE = EXTMCLR  // Master Clear Enable, RE3 is MCLR
#pragma config LPBOREN = OFF    // Low-power BOR disabled
#pragma config BOREN = ON       // Brown-out Reset enabled
#pragma config BORV = VBOR_2P45 // Brown-out Reset Voltage (2.45V)
#pragma config ZCD = OFF        // Zero-cross detect disabled
#pragma config PPS1WAY = ON     // PPSLOCK may be set once and cleared once
#pragma config STVREN = ON      // Stack Full/Underflow will cause Reset
#pragma config XINST = OFF      // Extended Instruction Set disabled
#pragma config WDTE = OFF       // WDT disabled
#pragma config LVP = OFF        // Low-Voltage Programming disabled
#pragma config CP = OFF         // User NVM program memory code protection off
#pragma config MVECEN = OFF     // Disable Vectored Interrupts (Use legacy mode)

#include <xc.h>
#include <stdbool.h>
#include <stdint.h>
#include "hal.h"
#include "pins.h"
#include "z80_bus.h"
#include "clock.h"
#include "command_queue.h"
#include "cmd.h"
#include "wait.h"

#define DEBOUNCE_THRESHOLD 2500

// Tracks the clock mode so the AUX button knows if it should dispatch cycles
static uint8_t is_sync_clock_active = 0;

// =========================================================================
// UART Packet Reader
// =========================================================================
static inline int read_uart(uint8_t packet[4]) {
    // Q43 uses INTCON0 for the Global Interrupt Enable
    INTCON0bits.GIE = 0;

    uint8_t sync_byte;
    if (UART_Read(&sync_byte) != 0 || sync_byte != SYNC_OK) {
        INTCON0bits.GIE = 1;
        return -1; // No valid packet start
    }

    // Block briefly to grab the 4 payload bytes
    for(int i = 0; i < 4; i++) {
        while (UART_Read(&packet[i]) != 0) {
            // Wait for byte to arrive in FIFO
        }
    }

    INTCON0bits.GIE = 1;
    return 0; // Success
}

// =========================================================================
// Status & Polling
// =========================================================================
static inline void Send_Status_Response() {
    cmd_status_t status = CQ_Get_Head_Status();

    if (status == STAT_DONE) {
        UART_Write(RESP_DONE);

        uint8_t read_data;
        if (CQ_Read_Head_Data(&read_data)) {
            UART_Write(read_data);
        }

        CQ_Pop_Head(); // Free the slot

    } else if (status == STAT_PROCESSING || status == STAT_PENDING) {
        UART_Write(RESP_PENDING);
    } else {
        UART_Write(RESP_IDLE);
    }
}

// =========================================================================
// Hardware Switch Debouncing
// =========================================================================
static inline void Process_Hardware_Inputs(uint8_t *debounced_aux, uint16_t *debounce_counter) {
    // Note: Ensure AUX_PIN_VAL is defined in pins.h as PORTBbits.RB4
    uint8_t raw_aux = AUX_PIN_VAL;

    if (raw_aux != *debounced_aux) {
        (*debounce_counter)++;
        if (*debounce_counter > DEBOUNCE_THRESHOLD) {
            *debounced_aux = raw_aux;
            *debounce_counter = 0;

            // Trigger on falling edge. Only dispatch if the auto-sync clock ISN'T running.
            if (*debounced_aux == 0 && !is_sync_clock_active) {
                CQ_Dispatch_Cycle();
            }
        }
    } else {
        *debounce_counter = 0;
    }
}

// =========================================================================
// Serial Command Dispatcher
// =========================================================================
static inline void Process_UART_Command(void) {
    uint8_t packet[4];

    if (read_uart(packet) < 0) {
        return;
    }

    uint8_t opcode = packet[0];
    uint16_t address = (((uint16_t)packet[1]) << 8) | packet[2];
    uint8_t param = packet[3];

    switch(opcode) {
        // --- ASYNC QUEUED COMMANDS ---
        case CMD_LD:
            if (CQ_Enqueue_MemRead(address)) UART_Write(RESP_QUEUED);
            else UART_Write(SYNC_NACK);
            break;

        case CMD_STORE:
            if (CQ_Enqueue_MemWrite(address, param)) UART_Write(RESP_QUEUED);
            else UART_Write(SYNC_NACK);
            break;

        case CMD_IN:
            if (CQ_Enqueue_IoRead(address)) UART_Write(RESP_QUEUED);
            else UART_Write(SYNC_NACK);
            break;

        case CMD_OUT:
            if (CQ_Enqueue_IoWrite(address, param)) UART_Write(RESP_QUEUED);
            else UART_Write(SYNC_NACK);
            break;

        // --- ASYNC POLLING / STEPPING ---
        case CMD_STEP:
            if (param == 0) param = 1;
            for (int i = 0; i < param; i++) {
                CQ_Dispatch_Cycle();
            }
            // Intentionally fall-through to report status

        case CMD_STATUS:
            Send_Status_Response();
            break;

        // --- CLOCK CONTROLS ---
        case CMD_CLK_AUTO:
            Z80_Clock_Start_FreeRun();
            is_sync_clock_active = 0;
            UART_Write(SYNC_OK);
            break;

        case CMD_CLK_SYNC:
            Z80_Clock_Start_Synchronized_Step();
            is_sync_clock_active = 1;
            UART_Write(SYNC_OK);
            break;

        case CMD_CLK_OFF:
            Z80_Clock_Stop_FreeRun();
            Z80_Clock_Stop_Synchronized_Step();
            is_sync_clock_active = 0;
            UART_Write(SYNC_OK);
            break;

        // --- IMMEDIATE COMMANDS ---
        case CMD_GHOST:
            Ghost(param);
            UART_Write(SYNC_OK);
            break;

        case CMD_SNAPSHOT:
            Z80_Bus_Snapshot();
            break;

        case CMD_BOOT:
            Z80_Boot_Sequence();
            UART_Write(SYNC_OK);
            break;

        default:
            UART_Write(SYNC_NACK);
            break;
    }
}

// =========================================================================
// Main Loop
// =========================================================================
void main(void) {
    System_Init();
    
    // Write an OK
    UART_Write(SYNC_OK);
    
    WAIT_Init();
    CQ_Init();         // Ensure queue memory is cleared
    Z80_Bus_Init();    // Boot into Ghost Mode
    Z80_Clock_Init();  // Setup PWMs and Timers

    uint8_t debounced_aux = 1; // Assume high (pulled-up) on boot
    uint16_t debounce_counter = 0;

    while(1) {
        Process_Hardware_Inputs(&debounced_aux, &debounce_counter);

        if (UART_Data_Available()) {
            Process_UART_Command();
        }
    }
}

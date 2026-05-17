/*
 * File:   main.c
 * Author: Marc Mosko
 */

#pragma config OSC = INTIO67    
#pragma config FCMEN = OFF      
#pragma config IESO = OFF       
#pragma config PWRT = ON        
#pragma config BOREN = SBORDIS  
#pragma config BORV = 3         
#pragma config WDT = OFF        
#pragma config MCLRE = ON       
#pragma config PBADEN = OFF     
#pragma config LVP = OFF        
#pragma config XINST = OFF      

#define _XTAL_FREQ 32000000 

#include <xc.h>
#include <stdbool.h>
#include "hal.h"        
#include "z80_bus.h"
#include "clock.h"      
#include "pins.h"
#include "command_queue.h"
#include "cmd.h" // Include new shared definitions

#define DEBOUNCE_THRESHOLD 2500 

static uint8_t is_auto_clock = 0;

static inline
int read_uart(uint8_t packet[4]) {
    INTCONbits.GIE = 0; 
    uint8_t sync_byte;
    if (UART_Read(&sync_byte) != 0 || sync_byte != SYNC_OK) {
        INTCONbits.GIE = 1; 
        return -1; 
    }
    uint8_t rx_err = 0;
    for(int i = 0; i < 4; i++) {
        if (UART_Read(&packet[i]) != 0) {
            rx_err = 1;
            break;
        }
    }
    INTCONbits.GIE = 1; 
    return rx_err;
}

static inline void Send_Status_Response() {
    cmd_status_t status = CQ_Get_Head_Status();
    
    if (status == STAT_DONE) {
        UART_Write(RESP_DONE);
        
        // Attempt to read data. If it returns true, it was a read operation!
        uint8_t read_data;
        if (CQ_Read_Head_Data(&read_data)) {
            UART_Write(read_data);
        }
        
        // Command fully delivered, clear it out of the queue!
        CQ_Pop_Head();
        
    } else if (status == STAT_PROCESSING || status == STAT_PENDING) {
        UART_Write(RESP_PENDING);
    } else {
        UART_Write(RESP_IDLE);
    }
}

static inline void Process_Hardware_Inputs(uint8_t *debounced_aux, uint16_t *debounce_counter) {
    uint8_t raw_aux = AUX_PIN_VAL;
        
    if (raw_aux != *debounced_aux) {
        (*debounce_counter)++;
        if (*debounce_counter > DEBOUNCE_THRESHOLD) {
            *debounced_aux = raw_aux;
            *debounce_counter = 0; 
            
            if (!is_auto_clock) {
                CQ_Dispatch_Cycle();
            }
        }
    } else {
        *debounce_counter = 0; 
    }
}

static inline void Process_UART_Command(void) {
    uint8_t packet[4];
    int rx_err = read_uart(packet);
    
    if (rx_err < 0) return; 
    if (rx_err > 0) {
        UART_Write(SYNC_NACK);
        return;
    }
    
    uint8_t opcode = packet[0];
    uint16_t address = (((uint16_t) packet[1]) << 8) | packet[2];
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
            
        case CMD_STATUS:
            Send_Status_Response();
            break;

        // --- IMMEDIATE COMMANDS ---
        case CMD_GHOST:
            Ghost(param);
            UART_Write(SYNC_OK);       
            break;
            
        case CMD_SNAPSHOT:
            Z80_Bus_Snapshot(); 
            break;
            
        case CMD_CLK_AUTO_START:
            Z80_Clock_Start_Auto();
            is_auto_clock = 1;
            UART_Write(SYNC_OK);     
            break;
            
        case CMD_CLK_AUTO_STOP:
            Z80_Clock_Stop_Auto();
            is_auto_clock = 0;
            UART_Write(SYNC_OK);     
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

void main(void) {
    System_Init(); 

    uint8_t debounced_aux = AUX_PIN_VAL;
    uint16_t debounce_counter = 0;

    while(1) {
        Process_Hardware_Inputs(&debounced_aux, &debounce_counter);
        
        if (UART_Data_Available()) {
            Process_UART_Command();
        }
    }
}
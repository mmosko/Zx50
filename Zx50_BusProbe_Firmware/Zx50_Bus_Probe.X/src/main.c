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


// Packet Opcodes
#define CMD_LD       0x01
#define CMD_STORE    0x02
#define CMD_IN       0x03
#define CMD_OUT      0x04
#define CMD_LDIR     0x05
#define CMD_SNAPSHOT 0x07  // Read state of the entire bus
#define CMD_GHOST    0x08  // 1 = Ghost (Release Bus), 0 = Unghost (Drive Bus)
#define CMD_STEP     0x11  // Clock control

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
#include "hal.h"
#include "z80_bus.h"
#include "clock.h"   // Included so we can pump the clock
#include "pins.h"    // Included so we can release RESET

#define CMD_LD       0x01
#define CMD_STORE    0x02
#define CMD_IN       0x03
#define CMD_OUT      0x04
#define CMD_LDIR     0x05
#define CMD_SNAPSHOT 0x07  
#define CMD_GHOST    0x08  
#define CMD_STEP     0x11  

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
#include "hal.h"
#include "z80_bus.h"
#include "clock.h"   

#define CMD_LD       0x01
#define CMD_STORE    0x02
#define CMD_IN       0x03
#define CMD_OUT      0x04
#define CMD_LDIR     0x05
#define CMD_SNAPSHOT 0x07  
#define CMD_GHOST    0x08  
#define CMD_STEP     0x11  

void main(void) {
    // Initialize pins safely to High-Z
    System_Init(); 

    // Safely reset the CPLD via the Z80 bus
    Z80_Boot_Sequence();

    uint8_t sync, opcode, addr_h, addr_l, param;

    while(1) {
        sync = UART_Read();
        if (sync != 0x5A) continue; 

        opcode = UART_Read();
        addr_h = UART_Read();
        addr_l = UART_Read();
        param  = UART_Read(); 

        uint16_t address = (((uint16_t) addr_h) << 8) | addr_l;

        switch(opcode) {
            case CMD_LD: {
                uint8_t read_val = Z80_Mem_Read(address);
                UART_Write(0x5A);     
                UART_Write(read_val); 
                break;
            }
            case CMD_STORE: {
                Z80_Mem_Write(address, param);
                UART_Write(0x5A);     
                break;
            }
            case CMD_IN: {
                uint8_t in_val = Z80_IO_Read(address);
                UART_Write(0x5A);     
                UART_Write(in_val);   
                break;
            }
            case CMD_OUT: {
                Z80_IO_Write(address, param);
                UART_Write(0x5A);     
                break;
            }
            case CMD_GHOST: {
                Ghost(param);
                UART_Write(0x5A);       
                break;
            }
            case CMD_SNAPSHOT: {
                Z80_Bus_Snapshot(); 
                break;
            }
            case CMD_LDIR: {
                for(uint8_t i=0; i<param; i++) {
                    uint8_t data_byte = UART_Read();
                    Z80_Mem_Write(address + i, data_byte);
                }
                UART_Write(0x5A);     
                break;
            }
            case CMD_STEP: {
                Z80_Clock_Pulse(); 
                UART_Write(0x5A);     
                break;
            }
        }
    }
}

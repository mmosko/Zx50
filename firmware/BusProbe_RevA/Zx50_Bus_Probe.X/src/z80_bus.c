#include <xc.h>
#include "hal.h"
#include "pins.h"
#include "clock.h"
#include "z80_bus.h"

static inline
void Z80_Write_Address(uint16_t address) {
    Expander_Write(U1_ADDR, REG_GPIOA, (uint8_t)(address >> 8));
    Expander_Write(U1_ADDR, REG_GPIOB, (uint8_t)(address & 0xFF));
}

void Z80_Mem_Write(uint16_t address, uint8_t data, t_cycle_t t_cycle) { 
    switch(t_cycle) {
        case CYCLE_T1: {
            // 1. Take control using your proven HAL logic
            Ghost(0); 
            
            // 2. Set Transceivers to B->A (PIC driving Z80 Bus)
            XCVR_CTRL_DIR_LAT = 0; 
            XCVR_DATA_DIR_LAT = 0; 
            Z80_DATA_DIR = 0x00;   // Output
           
            Z80_Write_Address(address);
            
            // ==========================================
            // --- T1 STATE ---
            // ==========================================
            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_MREQ_LAT = 0;      
            Z80_DATA_LAT = data;   
            break;
        }
        
        case CYCLE_T2: {
            // ==========================================
            // --- T2 STATE ---
            // ==========================================
            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_WR_LAT = 0;        
            break;
        }
        
        case CYCLE_T3: {
            // ==========================================
            // --- T3 STATE ---
            // ==========================================
            Z80_Clock_High();
            Z80_Clock_Low();
            
            Z80_WR_LAT   = 1;      
            asm("nop"); asm("nop"); asm("nop"); asm("nop");
            Z80_MREQ_LAT = 1;    

            // Completely release the bus back to safe Ghost Mode
            Ghost(1);
            break;
        }
        
        case CYCLE_T4:
            break;
    }
}

uint8_t Z80_Mem_Read(uint16_t address, t_cycle_t t_cycle) {
    uint8_t data = 0xFF;
    
    switch(t_cycle) {
        case CYCLE_T1: {
            Ghost(0);
            
            // Set Control B->A (Drive), Data A->B (Listen)
            XCVR_CTRL_DIR_LAT = 0;
            XCVR_DATA_DIR_LAT = 1; 
            Z80_DATA_DIR = 0xFF;   // Input
            
            Z80_Write_Address(address);

            // ==========================================
            // --- T1 STATE ---
            // ==========================================
            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_MREQ_LAT = 0;      
            Z80_RD_LAT   = 0;
            break;
        }
        case CYCLE_T2: {
            Z80_Clock_High();
            Z80_Clock_Low();
            break;
        }
        
        case CYCLE_T3: {
            // ==========================================
            // --- T3 STATE ---
            // ==========================================
            Z80_Clock_High();
            Z80_Clock_Low();

            data = Z80_DATA_VAL;   
            
            Z80_RD_LAT   = 1;  
            asm("nop");
            Z80_MREQ_LAT = 1;      

            Ghost(1);
            break;
        }
        
        case CYCLE_T4:
            break;
    }
                 
    return data;
}

static inline
void Z80_Toggle_Wait() {
    if (Z80_WAIT_DIR == 1) {
        Z80_WAIT_LAT = 0;
        Z80_WAIT_DIR = 0;
    } else {
        Z80_WAIT_LAT = 1;
        Z80_WAIT_DIR = 1;
    }
}

void Z80_IO_Write(uint16_t port_and_ah, uint8_t data, t_cycle_t t_cycle) {
    switch(t_cycle) {
        case CYCLE_T1: {
            Ghost(0);
            
            XCVR_CTRL_DIR_LAT = 0;
            XCVR_DATA_DIR_LAT = 0; // B to A
            Z80_DATA_DIR = 0x00;   // Output
            
            Z80_Write_Address(port_and_ah);

            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_DATA_LAT = data;   
            break;
        }
        case CYCLE_T2: {
            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_IORQ_LAT = 0; 
            Z80_WR_LAT   = 0;

            Z80_Toggle_Wait();
            break;
        }
        case CYCLE_T3: {
            Z80_Clock_High();
            Z80_Clock_Low();

            Z80_WR_LAT   = 1;
            asm("nop"); asm("nop"); asm("nop"); asm("nop");
            Z80_IORQ_LAT = 1;

            Ghost(1);
            break;
        }
        
        case CYCLE_T4:
            break;
    }
}

uint8_t Z80_IO_Read(uint16_t port_and_ah, t_cycle_t t_cycle) {
    uint8_t data = 0xFF;

    switch(t_cycle) {
        case CYCLE_T1: {
            Ghost(0);
            
            XCVR_CTRL_DIR_LAT = 0;
            XCVR_DATA_DIR_LAT = 1; // A to B
            Z80_DATA_DIR = 0xFF;   // Input
            
            Z80_Write_Address(port_and_ah);

            Z80_Clock_High();
            Z80_Clock_Low();
            break;
        }
        
        case CYCLE_T2: {
            Z80_Clock_High();
            Z80_Clock_Low();
            Z80_IORQ_LAT = 0; 
            Z80_RD_LAT   = 0; 
            
            Z80_Toggle_Wait();
            break;
        }
       
        case CYCLE_T3: {
            Z80_Clock_High();
            Z80_Clock_Low();

            data = Z80_DATA_VAL;   

            Z80_RD_LAT   = 1;
            asm("nop");
            Z80_IORQ_LAT = 1;

            Ghost(1);
            break;
        }
        
        case CYCLE_T4:
            break;
    }
    
    return data;
}

void Z80_Bus_Snapshot(void) {
    // 1. Ensure Expanders are in INPUT mode to prevent driving the bus
    Expander_Set_Input(U1_ADDR, REG_IODIRA);
    Expander_Set_Input(U1_ADDR, REG_IODIRB);
    
    // 2. Set Transceivers to A->B (Listen-Only: Backplane -> PIC)
    XCVR_DATA_DIR_LAT = 1; // A->B, Data
    XCVR_CTRL_DIR_LAT = 1; // A->B, Control
    
    // 3. Open the 74245 Transceivers
    XCVR_DATA_OE_LAT = 0;  // Enable U6
    XCVR_CTRL_OE_LAT = 0;  // Enable U7

    // 4. Sample the Bus
    uint8_t addr_h = Expander_Read(U1_ADDR, REG_GPIOA);
    uint8_t addr_l = Expander_Read(U1_ADDR, REG_GPIOB);
    
    Z80_DATA_DIR = 0xFF;   // Ensure PORTD is input
    uint8_t data_bus = Z80_DATA_VAL;
    
    uint8_t ctrl_porte = PORTE; // Contains ~RD, ~WR, ~M1
    uint8_t ctrl_portb = PORTB; // Contains ~WAIT, ~MREQ, ~IORQ, ~INT

    // 5. Close the 74245 (Return to Ghost Mode)
    XCVR_DATA_OE_LAT = 1;  // Disable U6
    XCVR_CTRL_OE_LAT = 1;  // Disable U7

    // 6. Transmit 6-byte response to Pico
    UART_Write(0x5A);       // ACK
    UART_Write(addr_h);
    UART_Write(addr_l);
    UART_Write(data_bus);
    UART_Write(ctrl_porte);
    UART_Write(ctrl_portb);
}

void Z80_Boot_Sequence(void) {
    // ==========================================
    // CPLD SYNC BOOT SEQUENCE
    // ==========================================
    
    // 1. Take control of the Control Bus to drive ~RESET
    XCVR_DATA_OE_LAT = 1;  // Keep Data Bus HIGH-Z to prevent collisions
    
    // Pre-load safe HIGH states for memory control
    Z80_MREQ_LAT = 1;
    Z80_IORQ_LAT = 1;
    Z80_RD_LAT   = 1;
    Z80_WR_LAT   = 1;
    Z80_M1_LAT   = 1;
    Z80_RESET_LAT = 0;     // Drive ~RESET LOW
    
    // Make them all outputs
    Z80_MREQ_DIR = 0;
    Z80_IORQ_DIR = 0;
    Z80_RD_DIR   = 0;
    Z80_WR_DIR   = 0;
    Z80_M1_DIR   = 0;
    Z80_RESET_DIR = 0;

    // Enable the Control Transceiver (B->A) to hit the backplane
    XCVR_CTRL_DIR_LAT = 0; 
    XCVR_CTRL_OE_LAT  = 0; 

    // 2. Pump the clock while RESET is LOW on the backplane
    for(int i = 0; i < 20; i++) {
        Z80_Clock_Pulse();
    }

    // 3. Release RESET (Drive HIGH)
    Z80_RESET_LAT = 1;

    // 4. Pump the clock so the CPLD advances into M_IDLE and releases ~WAIT
    for(int i = 0; i < 20; i++) {
        Z80_Clock_Pulse();
    }
    
    // 5. Explicitly enter Ghost Mode to release all transceivers
    Ghost(1);
}
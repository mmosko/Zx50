#include <xc.h>
#include "hal.h"
#include "pins.h"

#ifdef IN_SIMULATOR
#include "test_vectors.h"
#endif

// MCP23S17 Base Opcodes (0100 A2 A1 A0 R/W)
#define OPCODE_WRITE(addr)  ((uint8_t)(0x40 | ((addr) << 1)))
#define OPCODE_READ(addr)   ((uint8_t)(0x40 | ((addr) << 1) | 0x01))

// ==========================================
// SYSTEM INITIALIZATION
// ==========================================
void System_Init(void) {
    Clock_Init();
    GPIO_Init();
    UART_Init();
    SPI_Init();
    Expander_Init();
    Z80_Clock_Init();
}

void Clock_Init(void) {
    // Configure for 8 MHz, then enable 4x PLL to achieve 32 MHz.
    OSCCON = 0x70;          // IRCF = 111 (8 MHz), SCS = 00 (Primary oscillator)
    OSCTUNEbits.PLLEN = 1;  // Enable 4x PLL -> 32 MHz System Clock
    
#ifndef IN_SIMULATOR
    // The simulator does not model analog oscillator stabilization.
    // We only wait for the IOFS flag on real silicon.
    while(!OSCCONbits.IOFS); 
#endif
}

void GPIO_Init(void) {
    // Enable internal weak pull-ups on PORTB to prevent WAIT/INT hangs
    INTCON2bits.RBPU = 0;

    // 1. Disable all analog inputs
    ADCON1 = 0x0F; 
    CMCON  = 0x07; 

    // ---------------------------------------------------------
    // STEP 2: PRE-LOAD LATCHES WITH SAFE IDLE STATES
    // ---------------------------------------------------------
    // Set all ~OE pins HIGH (1) so transceivers boot up DISABLED
    XCVR_CTRL_OE_LAT = 1; 
    XCVR_DATA_OE_LAT = 1; 
    
    // Set transceivers to safely listen (A->B)
    XCVR_CTRL_DIR_LAT = 1; 
    XCVR_DATA_DIR_LAT = 1;

    // Pre-load Z80 control lines HIGH (Inactive)
    Z80_MREQ_LAT = 1;
    Z80_IORQ_LAT = 1;
    Z80_RD_LAT   = 1;
    Z80_WR_LAT   = 1;
    Z80_M1_LAT   = 1;
    
    // Hold the Z80 and CPLD in RESET (Active LOW)
    Z80_RESET_LAT = 0; 

    // ---------------------------------------------------------
    // STEP 3: CONFIGURE PIN DIRECTIONS
    // ---------------------------------------------------------
    // Transceiver controls must be outputs
    XCVR_CTRL_OE_DIR  = 0;
    XCVR_CTRL_DIR_DIR = 0;
    XCVR_DATA_OE_DIR  = 0;
    XCVR_DATA_DIR_DIR = 0;

    // Default Z80 bus to Ghost Mode (Inputs)
    TRISB = 0xFF; 
    TRISC = 0xFF; 
    TRISD = 0xFF; 
    TRISE = 0xFF; 
    
    // Disable PSP mode (parallel slave mode)
    TRISEbits.PSPMODE = 0;
            
    // EXCEPT: We must actively drive the RESET line!
    Z80_RESET_DIR = 0; 
}

void UART_Init(void) {
    // Configure EUSART for 1 Mbps at 32MHz Fosc.
    UART_TX_DIR = 0; // TX pin must be an OUTPUT for PIC18 Asynchronous mode
    UART_RX_DIR = 1; // RX pin must be input

    BAUDCON = 0x08;         // BRG16 = 1 (16-bit baud rate generator)
    TXSTA = 0x24;           // TXEN = 1 (Transmit Enable), BRGH = 1 (High Speed)
    RCSTA = 0x90;           // SPEN = 1 (Serial Port Enable), CREN = 1 (Continuous Receive)
    
    SPBRG = 7;              // Target 1 Mbps
    SPBRGH = 0;
}

void SPI_Init(void) {
    // SDI (RC4) is already an input from Ghost Mode.
    SPI_SCK_DIR = 0;   // SCK is output (Master Mode)
    SPI_SDO_DIR = 0;   // SDO is output

    // Shared ~CS pin for expanders (RA5)
    SPI_CS_LAT = 1;     // Default to high (idle)
    SPI_CS_DIR = 0;     // Set ~CS as output

    // Master Mode, Fosc/4 (8MHz SPI Clock)
    SSPSTAT = 0x40;         // SMP=0 (sample middle), CKE=1 (transmit active to idle)
    SSPCON1 = 0x20;         // SSPEN=1 (Enable), Master Fosc/4, CKP=0 (idle low)
}

/*
void Expander_Init(void) {
    // Broadcast a write to address 0x00 to set the HAEN (Hardware Address Enable) bit.
    Expander_Write(0x00, REG_IOCON, 0x08);

    // Now they respect their hardware pins. Ensure both are in INPUT mode.
    Expander_Set_Input(U1_ADDR, REG_IODIRA);
    Expander_Set_Input(U1_ADDR, REG_IODIRB);
    
    Expander_Set_Input(U13_ADDR, REG_IODIRA);
    Expander_Set_Input(U13_ADDR, REG_IODIRB);
}
*/

void Expander_Init(void) {
    // 1. HARDWARE RESET
    // Actively drive the Reset pin as an output
    EXP_RESET_DIR = 0;  
    
    // Yank the Expander reset lines LOW
    EXP_RESET_LAT = 0;  
    
    // Hold them in reset for a moment (use whatever delay function you have)
    // Even a simple loop of NOPs is fine if you don't have delays configured
    for(volatile int i=0; i<1000; i++); 
    
    // Drive the Reset line solidly HIGH (5V) and KEEP IT THERE
    EXP_RESET_LAT = 1;  
    for(volatile int i=0; i<1000; i++); // Wait for the chips to boot

    // 2. CONFIGURE HAEN
    // Broadcast a write to address 0x00 to set the HAEN bit.
    Expander_Write(0x00, REG_IOCON, 0x08);

    // 3. PARK AS INPUTS
    // Now they respect their hardware pins. Ensure both are in INPUT mode.
    Expander_Write(U1_ADDR, REG_IODIRA, 0xFF);
    Expander_Write(U1_ADDR, REG_IODIRB, 0xFF);
    
    Expander_Write(U13_ADDR, REG_IODIRA, 0xFF);
    Expander_Write(U13_ADDR, REG_IODIRB, 0xFF);
}


// ==========================================
// HARDWARE PRIMITIVES
// ==========================================
void UART_Write(uint8_t data) {
    // Wait for shift register to empty
    while (!TXSTAbits.TRMT); 
    TXREG = data;            
}

int UART_Read(uint8_t *output) {
#ifdef USE_SIMULATOR
    // Select your test vector here!
    static const uint8_t* current_test = TV_STORE_AND_READ;
    static uint16_t test_size = sizeof(TV_STORE_AND_READ);
    static uint16_t mock_index = 0;

    if (mock_index < test_size) {
        return current_test[mock_index++];
    } else {
        mock_index = 0; 
        __builtin_software_breakpoint();
        return 0x00;
    }
    return 0;
#else
    // TEMPORAL FRAMING TIMEOUT
    // At 32 MHz, one instruction cycle is 125ns. 
    // A loop of 4000 iterations * ~4 instructions per loop = ~2 milliseconds.
    // At 1 Mbps, a byte takes 10us. If we wait 2ms, the sender has definitely stopped.
    uint16_t timeout = 4000; 

    // Wait for the Receive Interrupt Flag (Data available in RCREG)
    while (!PIR1bits.RCIF) {
        
        // SAFETY MECHANISM 1: Overrun Error (OERR) Lockup Protection
        // Happens if the Pico sends data while the PIC is stuck inside the Timer0 ISR.
        if (RCSTAbits.OERR) {
            RCSTAbits.CREN = 0; // Disable receiver (flushes the corrupted hardware FIFO)
            asm("nop");         // Micro-delay for hardware to settle
            RCSTAbits.CREN = 1; // Re-enable receiver to listen for the next packet
            return 1;           // 1 = ERROR
        }
        
        // SAFETY MECHANISM 2: False SYNC Deadlock Breaker
        // If we read a false 0x5A from a broken packet, the system will infinitely 
        // wait for the rest of the payload. This timeout guarantees we give up 
        // and return a NACK to the Pico so the state machine can reset.
        if (--timeout == 0) {
            return 1;           // 1 = ERROR
        }
    } 

    // SAFETY MECHANISM 3: Framing Error (FERR) Protection
    // Happens if baud rates are mismatched or the line suffers electrical noise.
    if (RCSTAbits.FERR) {
        volatile uint8_t dummy = RCREG; // Reading RCREG clears the FERR bit in hardware
        return 1;                       // 1 = ERROR
    }

    // Pass the safely validated byte out to the caller
    *output = RCREG; 
    return 0;        // 0 = SUCCESS
#endif
}

uint8_t UART_Data_Available(void) {
#ifdef IN_SIMULATOR
    // In the simulator, data is always "available" from the mock array
    return 1; 
#else
    // 1. Check for the deadly Overrun Error FIRST
    if (RCSTAbits.OERR) {
        RCSTAbits.CREN = 0; // Disable receiver (flushes the corrupted FIFO)
        asm("nop");         // Micro-delay
        RCSTAbits.CREN = 1; // Re-enable receiver
        
        return 0; // We just flushed the buffer, so no valid data is available
    }

    // 2. REAL HARDWARE: Returns 1 if the RX FIFO has valid unread data
    return PIR1bits.RCIF; 
#endif
}

uint8_t SPI_Transfer(uint8_t data) {
    SSPBUF = data;           
#ifdef IN_SIMULATOR
    // MOCK: Give the simulator a few cycles to pretend the transfer happened
    for(volatile int i = 0; i < 10; i++); 
#else
    // REAL HARDWARE: Wait for the Buffer Full (BF) bit
    while (!SSPSTATbits.BF); 
#endif
    return SSPBUF;           
}

void Expander_Set_Input(uint8_t hw_addr, uint8_t reg_addr) {
    Expander_Write(hw_addr, reg_addr, 0xFF);
}

void Expander_Set_Output(uint8_t hw_addr, uint8_t reg_addr) {
    Expander_Write(hw_addr, reg_addr, 0x00);
}


void Expander_Write(uint8_t hw_addr, uint8_t reg_addr, uint8_t data) {
    SPI_CS_LAT = 0;      // Pull ~CS low 
    
    SPI_Transfer(OPCODE_WRITE(hw_addr)); 
    SPI_Transfer(reg_addr);  
    SPI_Transfer(data);      
    
    SPI_CS_LAT = 1;      // Pull ~CS high
}

uint8_t Expander_Read(uint8_t hw_addr, uint8_t reg_addr) {
    uint8_t data;

    SPI_CS_LAT = 0;      // Pull ~CS low 
    
    SPI_Transfer(OPCODE_READ(hw_addr)); 
    SPI_Transfer(reg_addr);  
    data = SPI_Transfer(0x00); // Send dummy byte to clock in the read data
    
    SPI_CS_LAT = 1;      // Pull ~CS high
    return data;
}

// Note: We don't drive the specific control lines low here, 
// we just configure them as outputs so Mem_Write can use them.
// They should idle HIGH.
void HAL_Control_Inactive() {
    Z80_MREQ_LAT = 1;
    Z80_WR_LAT   = 1;
    Z80_RD_LAT   = 1;
    Z80_IORQ_LAT = 1;
}

// param = 1 to ghost mode, 0, to unghost
void Ghost(uint8_t param) {
    if (param == 1) {
        // GHOST MODE: Release the bus (High-Z)
        Z80_DATA_DIR = 0xFF; // Set PIC Data Bus to Input
        Z80_MREQ_DIR = 1;    // Release ~MREQ
        Z80_WR_DIR   = 1;    // Release ~WR
        Z80_RD_DIR   = 1;    // Release ~RD
        Z80_IORQ_DIR = 1;    // Release ~IORQ

        XCVR_DATA_OE_LAT = 1; // Disable U6
        XCVR_CTRL_OE_LAT = 1; // Disable U7
        
        // Set Address bus to input
        Expander_Set_Input(U1_ADDR, REG_IODIRA);
        Expander_Set_Input(U1_ADDR, REG_IODIRB);

    } else {
        // UNGHOST MODE: Take control of the bus
                
        // Set Address bus to output
        Expander_Set_Output(U1_ADDR, REG_IODIRA);
        Expander_Set_Output(U1_ADDR, REG_IODIRB);

        HAL_Control_Inactive();

        Z80_MREQ_DIR = 0; // Drive ~MREQ
        Z80_WR_DIR   = 0; // Drive ~WR
        Z80_RD_DIR   = 0; // Drive ~RD
        Z80_IORQ_DIR = 0; // Drive ~IORQ
            
        XCVR_DATA_OE_LAT = 0; // Enable U6
        XCVR_CTRL_OE_LAT = 0; // Enable U7
        
        // Safe default is DATA is INPUT.  Only set to OUTPUT during a WRITE
        Z80_DATA_DIR = 0xFF; 

    }
}

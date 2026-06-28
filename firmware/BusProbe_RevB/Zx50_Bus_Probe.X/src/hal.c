#include <xc.h>
#include "hal.h"

// MCP23S17 Base Opcodes (0100 A2 A1 A0 R/W)
static const uint8_t OPCODE_WRITE = 0x40;
static const uint8_t OPCODE_READ = 0x41;

static void SPI1_Initialize(void);
static void GPIO_Init(void);
static void UART_Init(void);
static void Expander_Init(void);

// ==========================================
// SYSTEM INITIALIZATION
// ==========================================
void System_Init(void) {
    // Oscillator, GPIO, and peripheral initialization
    OSCCON1 = 0x60; // HFINTOSC with HFFRQ = 64 MHz
    OSCFRQ = 0x08;  // Set HFFRQ to 64 MHz

    GPIO_Init();
    UART_Init();
    SPI1_Initialize();
    Expander_Init();
}

static void GPIO_Init(void) {
    // --- 1. Disable all analog inputs ---
    ANSELA = 0x00;
    ANSELB = 0x00;
    ANSELC = 0x00;

    // --- 2. Configure Open-Drain Outputs for Bus Safety ---
    ODCONBbits.ODCB0 = 1; // Z80_INT
    ODCONBbits.ODCB1 = 1; // Z80_WAIT
    ODCONBbits.ODCB3 = 1; // Z80_BUSRQ

    // --- 3. Set Initial Latch States ---
    EXP_CS_LAT = 1;        // Deselect all expanders (RA5)
    EXP_RESET_LAT = 1;     // Hold expanders out of reset (RA4)
    
    // Disable all transceivers on boot by driving *OE High
    DATA_XCVR_OE_LAT = 1;
    ADDR_XCVR_OE_LAT = 1;
    SHADOW_XCVR_OE_LAT = 1;

    Z80_BUSRQ_LAT = 1;     
    Z80_WAIT_LAT = 1;      
    Z80_INT_LAT = 1;       

    Z80_CLK_LAT = 0;       
    Z80_MCLK_LAT = 0;

    // --- 4. Set Pin Directions ---
    TRISA = 0x00; // PORTA is strictly Output (Transceivers + Expander CS/RST)
    TRISB = 0xFF; // Default inputs
    TRISC = 0xFF; // Default inputs

    // SPI Pins
    SPI_SCK_DIR = 0; 
    SPI_SDO_DIR = 0; 

    // UART Pins
    PICO_TX_DIR = 0; 
    PICO_RX_DIR = 1; 

    // Z80 Control Pins
    Z80_BUSRQ_DIR = 0;
    Z80_WAIT_DIR = 0;
    Z80_INT_DIR = 0;

    // Heartbeat LED Setup
    ANSELBbits.ANSELB5 = 0; 
    TRISBbits.TRISB5 = 0;   
    LATBbits.LATB5 = 1;     
}

static void UART_Init(void) {
    // 1. Avert the TRIS and Analog Traps explicitly for RC6/RC7
    ANSELCbits.ANSELC6 = 0; // TX digital
    ANSELCbits.ANSELC7 = 0; // RX digital
    TRISCbits.TRISC6 = 0;   // TX is output (Pin 17)
    TRISCbits.TRISC7 = 1;   // RX is input (Pin 18)

    // 2. PPS (Peripheral Pin Select) Routing
    RC6PPS = 0x20;      // Route UART1 TX to physical pin RC6
    U1RXPPS = 0x17;     // Route physical pin RC7 to UART1 RX

    // 3. Hardware Configuration
    U1CON0bits.MODE = 0b0000; // 8-bit async mode
    U1CON0bits.BRGS = 1;      // High-Speed Mode (Divide-by-4 formula)
    U1BRG = 15;               // 64MHz / (4 * (15 + 1)) = 1 Mbps

    // 4. Enable Transmitter and Receiver FIRST
    U1CON0bits.TXEN = 1; 
    U1CON0bits.RXEN = 1; 

    // 5. Turn ON the UART LAST
    U1CON1bits.ON = 1;  
}

static void SPI1_Initialize(void)
{
    // 1. Ensure SPI is disabled before making configuration changes
    SPI1CON0bits.EN = 0;

    // =========================================================================
    // 2. PPS (PERIPHERAL PIN SELECT) ROUTING
    // (Note: Adjust the 0x13/0x14/0x15 values to match your Zx50 RevB netlist)
    // =========================================================================

    // Example: Assuming SCK on RC3, SDI on RC4, SDO on RC5
    RC3PPS = 0x31;        // Route SPI1 SCK output to physical pin RC3
    RC5PPS = 0x32;        // Route SPI1 SDO output to physical pin RC5

    SPI1SDIPPS = 0x14;    // Route physical pin RC4 input to SPI1 SDI

    // ⚠️ THE Q43 TRAP: Even in Master mode, the SPI hardware needs to monitor
    // its own clock line. You MUST route the SCK input PPS to the same pin
    // you routed the SCK output to!
    SPI1SCKPPS = 0x13;    // Route physical pin RC3 input back to SPI1 SCK

    // =========================================================================
    // 3. CLOCK & BAUD RATE SETTINGS
    // =========================================================================

    SPI1CLKbits.CLKSEL = 0b0000; // Source clock = FOSC

    // SPI Frequency = FOSC / (2 * (BAUD + 1))
    // 64MHz / (2 * (3 + 1)) = 8 MHz (Safe for MCP23S17 10MHz limit)
    SPI1BAUD = 0x03;

    // =========================================================================
    // 4. SPI MODULE CONFIGURATION (Mode 0,0)
    // =========================================================================

    SPI1CON1bits.SMP = 0;   // Sample SDI at the middle of data output time
    SPI1CON1bits.CKE = 1;   // Output data changes on transition from active to idle
    SPI1CON1bits.CKP = 0;   // Idle state for SCK is a low level

    SPI1CON0bits.LSBF = 0;  // MSb first (Required by MCP23S17)
    SPI1CON0bits.MST = 1;   // Master mode
    SPI1CON0bits.BMODE = 1; // Byte Transfer mode (legacy style read/write)

    // =========================================================================
    // 5. ENABLE THE PERIPHERAL
    // =========================================================================

    // FULL DUPLEX MODE: Require both Transmit and Receive paths
    SPI1CON2bits.TXR = 1;
    SPI1CON2bits.RXR = 1;

    SPI1CON0bits.EN = 1;    // Enable SPI module    
}

static void Expander_Init(void) {
    // --- Hardware Reset the Expanders ---
    EXP_RESET_LAT = 0;
    __delay_ms(1);
    EXP_RESET_LAT = 1;
    __delay_ms(1);

    // --- Configure All Three Expanders ---
    // Enable hardware address pins so they respond to their unique CS lines
    Expander_Write(EXP_ADDR_HW_ADDR, REG_IOCON, 0x08);
    Expander_Write(EXP_DATA_HW_ADDR, REG_IOCON, 0x08);
    Expander_Write(EXP_SHADOW_HW_ADDR, REG_IOCON, 0x08);

    // --- Set Port Directions (Default to all inputs) ---
    // U1: Address Bus (A0-A15) - Always inputs from Z80
    Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRA, 0xFF);
    Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRB, 0xFF);
    Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0xFF);
    Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRB, 0xFF);
    Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRA, 0xFF);
    Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRB, 0xFF);
}

// ==========================================
// HARDWARE PRIMITIVES
// ==========================================
void UART_Write(uint8_t data) {
    while(!PIR4bits.U1TXIF);
    U1TXB = data;
}


int UART_Read(uint8_t *output) {
    // If the hardware FIFO overflows, safely flush it
    if (U1ERRIRbits.U1RXFOIF) {
        // Drain the FIFO to clear the overflow condition
        while (PIR4bits.U1RXIF) {
            volatile uint8_t dummy = U1RXB;
        }
        // Manually clear the flag just to be safe
        U1ERRIRbits.U1RXFOIF = 0; 
        return 1;
    }
    
    if (PIR4bits.U1RXIF) {
        *output = U1RXB;
        return 0;
    }
    return 1;
}

uint8_t UART_Data_Available(void) {
    return PIR4bits.U1RXIF;
}

uint8_t SPI_Transfer(uint8_t data) {
    // Write data to the transmit buffer to start the clock
    SPI1TXB = data;

    // Wait for the hardware to receive the byte and flag the RX FIFO
    while(!PIR3bits.SPI1RXIF) {
        // Wait for transfer to complete
    }

    // Reading SPI1RXB automatically clears the SPI1RXIF flag
    return SPI1RXB;
}

void Expander_Write(uint8_t hw_addr, uint8_t reg_addr, uint8_t data) {
    EXP_CS_LAT = 0; // Assert Shared CS

    uint8_t opcode = (uint8_t)(OPCODE_WRITE | (hw_addr << 1));
    
    SPI_Transfer(opcode);
    SPI_Transfer(reg_addr);
    SPI_Transfer(data);

    EXP_CS_LAT = 1; // De-assert Shared CS
}

uint8_t Expander_Read(uint8_t hw_addr, uint8_t reg_addr) {
    uint8_t data;

    EXP_CS_LAT = 0; // Assert Shared CS

    uint8_t opcode = (uint8_t)(OPCODE_READ | (hw_addr << 1));
    
    SPI_Transfer(opcode);
    SPI_Transfer(reg_addr);
    data = SPI_Transfer(0x00); 

    EXP_CS_LAT = 1; // De-assert Shared CS

    return data;
}

#include <xc.h>
#include "hal.h"
#include "z80_bus.h"
#include "clock.h"
#include "wait.h"

// ==========================================
// Bus Initialization
// ==========================================

void Z80_Bus_Init(void) {
    // On startup, enter Ghost mode to ensure the probe is non-intrusive.
    Ghost(1);
}

// ==========================================
// Bus Control
// ==========================================

static inline uint8_t Reverse_Byte(uint8_t b) {
    b = (uint8_t)(((b & 0xF0) >> 4) | ((b & 0x0F) << 4));
    b = (uint8_t)(((b & 0xCC) >> 2) | ((b & 0x33) << 2));
    b = (uint8_t)(((b & 0xAA) >> 1) | ((b & 0x55) << 1));
    return b;
}


void Ghost(uint8_t enable) {
    // Always enable the transceivers by driving their *OE pins LOW
    LATAbits.LATA0 = 0; // Data Bus *OE
    LATAbits.LATA2 = 0; // Addr/Ctrl Bus *OE
    LATAbits.LATA6 = 0; // Shadow Bus *OE

    if (enable) {
        // --- GHOST MODE (LISTEN) ---
        LATAbits.LATA1 = 1; // Data DIR: Inward
        LATAbits.LATA3 = 1; // Addr/Ctrl DIR: Inward
        LATAbits.LATA7 = 1; // Shadow DIR: Inward

        // 2. Configure all expander ports as INPUTS
        Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRA, 0xFF);
        Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRB, 0xFF);
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0xFF);
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRB, 0xFF);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRA, 0xFF);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRB, 0xFF);

    } else {
        // --- CONTROL MODE (DRIVE) ---
        LATAbits.LATA1 = 0; // Data DIR: Outward
        LATAbits.LATA3 = 0; // Addr/Ctrl DIR: Outward
        LATAbits.LATA7 = 0; // Shadow DIR: Outward

        // 2. Configure all expander ports as OUTPUTS
        Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRA, 0x00);
        Expander_Write(EXP_ADDR_HW_ADDR, REG_IODIRB, 0x00);
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0x00);
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRB, 0x00);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRA, 0x00);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_IODIRB, 0x00);

        // 3. Drive a safe, inactive state on all buses
        Expander_Write(EXP_ADDR_HW_ADDR, REG_GPIOA, 0x00);
        Expander_Write(EXP_ADDR_HW_ADDR, REG_GPIOB, 0x00);
        Expander_Write(EXP_DATA_HW_ADDR, REG_GPIOA, 0x00);
        Expander_Write(EXP_DATA_HW_ADDR, REG_GPIOB, 0xFF);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_GPIOA, 0x00);
        Expander_Write(EXP_SHADOW_HW_ADDR, REG_GPIOB, 0xFF);
    }
}

// ==========================================
// Internal Helper Functions
// ==========================================

static inline void Z80_Set_Address(uint16_t address) {
    // GPA is A0-A7 (Low Byte). GPB is A8-A15 (High Byte).
    Expander_Write(EXP_ADDR_HW_ADDR, REG_GPIOA, (uint8_t)(address & 0xFF));
    Expander_Write(EXP_ADDR_HW_ADDR, REG_GPIOB, (uint8_t)(address >> 8));
}

static inline void Z80_Set_Data(uint8_t data) {
    // Reverse the bits to compensate for PCB routing
    Expander_Write(EXP_DATA_HW_ADDR, REG_GPIOA, Reverse_Byte(data));
}

static inline uint8_t Z80_Get_Data(void) {
    // Read the bits and reverse them back to normal
    return Reverse_Byte(Expander_Read(EXP_DATA_HW_ADDR, REG_GPIOA));
}

static inline void Z80_Set_Control(uint8_t mreq, uint8_t iorq, uint8_t rd, uint8_t wr) {
    uint8_t ctrl_byte = 0xFF;
    if (mreq == 0) ctrl_byte &= ~(1 << Z80_MREQ_N_PIN);
    if (iorq == 0) ctrl_byte &= ~(1 << Z80_IORQ_N_PIN);
    if (rd == 0)   ctrl_byte &= ~(1 << Z80_RD_N_PIN);
    if (wr == 0)   ctrl_byte &= ~(1 << Z80_WR_N_PIN);
    Expander_Write(EXP_DATA_HW_ADDR, REG_GPIOB, ctrl_byte);
}

// ==========================================
// Public Z80 Bus Functions
// ==========================================

// These functions assume Ghost(0) has already been called.

void Z80_Mem_Write(uint16_t address, uint8_t data, t_cycle_t cycle) {
    if (cycle == CYCLE_T1) {
        Z80_Set_Address(address);
        Z80_Set_Data(data);
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(0, 1, 1, 1);
    } else if (cycle == CYCLE_T2) {
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(0, 1, 1, 0);
    } else if (cycle == CYCLE_T3) {
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 1, 1, 1);
    }
}

uint8_t Z80_Mem_Read(uint16_t address, t_cycle_t cycle) {
    uint8_t data = 0xFF;
    if (cycle == CYCLE_T1) {
        Z80_Set_Address(address);
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(0, 1, 1, 1);
    } else if (cycle == CYCLE_T2) {
        // ⚠️ CRITICAL: We are about to assert ~RD.
        // We MUST turn our Data Transceiver around to LISTEN (Inward)
        // and switch the Expander to INPUT so we don't fight the RAM chip!
        LATAbits.LATA1 = 1;
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0xFF);

        Z80_Generate_Single_Pulse();
        Z80_Set_Control(0, 1, 0, 1);
    } else if (cycle == CYCLE_T3) {
        data = Z80_Get_Data();
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 1, 1, 1);

        // Restore Drive state for the next cycle
        LATAbits.LATA1 = 0;
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0x00);
    }
    return data;
}

void Z80_IO_Write(uint16_t port_and_ah, uint8_t data, t_cycle_t cycle) {
    if (cycle == CYCLE_T1) {
        Z80_Set_Address(port_and_ah);
        Z80_Set_Data(data);
        Z80_Generate_Single_Pulse();
    } else if (cycle == CYCLE_T2) {
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 0, 1, 0);
        WAIT_Assert();
    } else if (cycle == CYCLE_T3) {
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 1, 1, 1);
        WAIT_Deassert();
    }
}


uint8_t Z80_IO_Read(uint16_t port_and_ah, t_cycle_t cycle) {
    uint8_t data = 0xFF;
    if (cycle == CYCLE_T1) {
        Z80_Set_Address(port_and_ah);
        Z80_Generate_Single_Pulse();
    } else if (cycle == CYCLE_T2) {
        // We are about to assert ~RD.
        // We MUST turn our Data Transceiver around to LISTEN (Inward)
        // and switch the Expander to INPUT
        LATAbits.LATA1 = 1;
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0xFF);

        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 0, 0, 1);
        WAIT_Assert();
    } else if (cycle == CYCLE_T3) {
        data = Z80_Get_Data();
        Z80_Generate_Single_Pulse();
        Z80_Set_Control(1, 1, 1, 1);
        WAIT_Deassert();
        // Restore Drive state for the next cycle
        LATAbits.LATA1 = 0;
        Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRA, 0x00);
    }
    return data;
}

void Z80_Bus_Snapshot(void) {
    Ghost(1); // Ensure we are in listen-only mode

    uint8_t addr_h = Expander_Read(EXP_ADDR_HW_ADDR, REG_GPIOA);
    uint8_t addr_l = Expander_Read(EXP_ADDR_HW_ADDR, REG_GPIOB);
    uint8_t data_bus = Expander_Read(EXP_DATA_HW_ADDR, REG_GPIOA);
    uint8_t ctrl_bus = Expander_Read(EXP_DATA_HW_ADDR, REG_GPIOB);

    UART_Write(0x5A);
    UART_Write(addr_h);
    UART_Write(addr_l);
    UART_Write(data_bus);
    UART_Write(ctrl_bus);
    UART_Write(0x00);
}

void Z80_Boot_Sequence(void) {
    Ghost(0); // Take control of the bus

    Expander_Write(EXP_DATA_HW_ADDR, REG_IODIRB, (uint8_t)~(1U << Z80_RESET_N_PIN));
    
    for(int i = 0; i < 20; i++) {
        Z80_Generate_Single_Pulse();
    }

    Expander_Write(EXP_DATA_HW_ADDR, REG_GPIOB, 0xFF);

    for(int i = 0; i < 20; i++) {
        Z80_Generate_Single_Pulse();
    }
    
    Ghost(1); // Release the bus
}

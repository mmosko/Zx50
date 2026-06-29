; -- Memory Table --

; Start just after the monitor program
CLI_BUFFER      EQU _END_OF_ROM + 1
CLI_MAX_LEN     EQU 128
; We reserve the last byte for the NULL terminator
CLI_BUFFER_END  EQU CLI_BUFFER + CLI_MAX_LEN - 1

; The last address used for "D" command
LAST_DUMP_ADDR  EQU CLI_BUFFER_END + 1

; This measures to the end of the monitor scratch pad.  It is
; used to zero out the RAM after the ROM is copied to RAM.
MONITOR_STORAGE_SIZE EQU LAST_DUMP_ADDR + 2 - _END_OF_ROM

; Start the stack pointer at 8K and work down
; This is the end of logical page 1
STACK_POINTER   EQU 0x2000

; --- I/O Port Definitions ---
CTC_CH0     EQU 0x80    ; CTC Channel 0 (Drives SIO Port A Clock)
CTC_CH1     EQU 0x81    ; CTC Channel 1 (Drives SIO Port B Clock)

SIO_A_CMD   EQU 0x86    ; SIO Port A Control/Command Register
SIO_B_CMD   EQU 0x87    ; SIO Port B Control/Command Register

SIO_A_DAT   EQU 0x84    ; SIO Port A Data Register
SIO_B_DAT   EQU 0x85    ; SIO Port B Data Register

CONSOLE_CMD EQU SIO_A_CMD   ; The serial port for main console I/O is SIO Port A (FTDI)
CONSOLE_DAT EQU SIO_A_DAT   ;   

DEBUG_CMD   EQU SIO_B_CMD   ; The serial port for debug console I/O
DEBUG_DAT   EQU SIO_B_DAT   ;

LCD_PORT    EQU 0x50    ; Pico Front Panel LCD I/O Port
MMU_PORT    EQU 0x30    ; Pico MMU I/O Port

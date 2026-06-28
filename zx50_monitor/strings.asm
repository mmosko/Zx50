; =============================================================================
; Front Panel LCD String Table
; Format: [Length Byte], [0x01 Command], [ASCII Text], [0x0A Newline]
; =============================================================================

MSG_MEM_INIT:
    DB 10               ; Length: 1 (cmd) + 8 (text) + 1 (newline) = 10
    DB 0x01             ; Pico LCD Clear/Text Command
    DB "Mem Init"
    DB 0x0A             ; '\n'

MSG_SIO_READY:
    DB 16               ; Length: 1 (cmd) + 8 (text) + 1 (newline) + 6 (line 2)= 10
    DB 0x01
    DB "SIO Init"
    DB 0x0A
    DB "Ready"
    DB 0x0A

MSG_LCD_HALT:
    DB 6               ; Length: 6
    DB 0x01
    DB "HALT"
    DB 0x0A

; =============================================================================
; Serial String Table (Null-Terminated)
; =============================================================================
MSG_CONSOLE_BANNER:
    DB 0x0D, 0x0A, "========================", 0x0D, 0x0A
    DB " Zx50 Monitor v1.0", 0x0D, 0x0A
    DB "========================", 0x0D, 0x0A, 0x00

MSG_DEBUG_BANNER:
    DB 0x0D, 0x0A, "[SYS] Debug Trace Port Active.", 0x0D, 0x0A, 0x00

MSG_DEBUG_LINE:
    DB "[SYS] CMD Rx: ", 0x00

MSG_CRLF:
    DB 0x0D, 0x0A, 0x00

MSG_QUIT:
    DB "Program halted!", 0x0D, 0x0A, 0x00

; =============================================================================
; CLI String Table (Null-Terminated)
; =============================================================================

MSG_PROMPT:
    DB "Zx50>", 0x00    ; CP/M DDT style prompt

MSG_UNKNOWN:
    DB "?", 0x0D, 0x0A, 0x00    ; Standard CP/M error

MSG_HELP:
    DB "Commands:", 0x0D, 0x0A
    DB "  D[start][,end] - Display Memory", 0x0D, 0x0A
    DB "  Q              - Quit (halt)", 0x0D, 0x0A
    DB "  ?, H           - This help menu", 0x0D, 0x0A, 0x00

    ; DB "  L[start]       - Disassemble (List) Memory", 0x0D, 0x0A
    ; DB "  G[start]       - Go (Execute)", 0x0D, 0x0A

MSG_DUMP_STUB:
    DB "Dump command triggered!", 0x0D, 0x0A, 0x00

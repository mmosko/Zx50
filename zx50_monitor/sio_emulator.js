// ============================================================================
// Zx50 SIO Serial Port Emulator with Custom UI
// ============================================================================

let rxQueue = [];
let terminalConnected = false;

// Triggered automatically by DeZog the exact millisecond the HTML UI loads
API.uiReady = () => {
    terminalConnected = true;
    API.log("UI Connected. Asserting Hardware DTR...");
};

// --- Receive Keystrokes FROM the HTML UI ---
API.receivedFromCustomUi = (msg) => {
    API.log("JS Rx Key: " + msg.char); // Prove we got the keystroke!
    if (msg.command === 'tx') {
        rxQueue.push(msg.char);
    }
};

API.readPort = (port) => {
    let p = port & 0xFF; 

    // SIO Port A Command (CONSOLE_CMD - 0x86)
    if (p === 0x86) {
        // HARDWARE FLOW CONTROL:
        // Pretend Tx Buffer is full (0x00) until the HTML UI tells us it's listening.
        // This stalls the Z80 safely at the Console_Tx loop until the UI loads!
        let status = terminalConnected ? 0x04 : 0x00; 
        
        if (rxQueue.length > 0) {
            status |= 0x01; // Rx Character Available
        }
        return status; 
    }

    // SIO Port A Data (CONSOLE_DAT - 0x84)
    if (p === 0x84) {
        if (rxQueue.length > 0) {
            return rxQueue.shift(); // Pop the oldest character off the queue
        }
        return 0x00;
    }

    // SIO Port B Command (DEBUG_CMD - 0x87)
    if (p === 0x87) return 0x04; 

    return undefined; 
};

API.writePort = (port, value) => {
    let p = port & 0xFF;
    
    if (p === 0x84) { 
        // serial A console
        API.sendToCustomUi({ command: 'con', char: value });
    } else if (p === 0x85) {
        // serial B debug 
        API.sendToCustomUi({ command: 'dbg', char: value });
    } else if (p === 0x50) {
        // Front Panel LCD (0x50)
        API.sendToCustomUi({ command: 'lcd', char: value });
    }
};

// ============================================================================
// Zx50 CTC Emulator (Channel 3 - 100Hz Tick)
// ============================================================================

const TSTATES_PER_TICK = 50000; // 5MHz ZCLK / 100Hz = 50,000 T-States
let nextInterruptTstate = TSTATES_PER_TICK;

// Triggered automatically by DeZog after every Z80 instruction
API.tick = () => {
    // API.tstates contains the absolute total of CPU cycles executed since boot
    if (API.tstates >= nextInterruptTstate) {
        nextInterruptTstate += TSTATES_PER_TICK;
        API.log("TICK: " + API.tstates + " Next Interrupt: " + nextInterruptTstate);
        
        // Assert the /INT line and place the CH3 Vector (0x06) on the data bus!
        API.generateInterrupt(false, 0x06);
    }
};

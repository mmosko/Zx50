// ============================================================================
// Zx50 SIO Emulator (Continuous Level-Triggered Architecture)
// ============================================================================

let rxQueue = [];
let terminalConnected = false;

let sioA_PTR = 0;
let sioB_PTR = 0;
let sioA_WR1 = 0x00; 
let sioB_WR1 = 0x00; 
let sioB_WR2 = 0x00; 
let txA_IntPending = true; 

let pendingInterrupts = []; 

function requestInterrupt(vector, source) {
    if (!pendingInterrupts.includes(vector)) {
        API.log(`INT: Latching 0x${vector.toString(16).toUpperCase()} (${source})`);
        pendingInterrupts.push(vector);
    }
}

function cancelInterrupt(vector) {
    pendingInterrupts = pendingInterrupts.filter(v => v !== vector);
}

function checkInterrupts() {
    let sav = (sioB_WR1 & 0x04) !== 0;

    // 1. Evaluate SIO Rx Interrupt (Level-Triggered)
    let rxMode = (sioA_WR1 & 0x18);
    if (rxMode !== 0x00 && rxQueue.length > 0) {
        let vector = sav ? (sioB_WR2 | 0x0C) : sioB_WR2;
        requestInterrupt(vector, "Rx Level Trigger");
    }

    // 2. Evaluate SIO Tx Interrupt (Level-Triggered)
    let txIntEnabled = (sioA_WR1 & 0x02) !== 0;
    if (txIntEnabled && txA_IntPending) {
        let vector = sav ? (sioB_WR2 | 0x08) : sioB_WR2;
        requestInterrupt(vector, "Tx Level Trigger");
    }

    // 3. Drain the Interrupt Latch (Oldest first)
    if (pendingInterrupts.length > 0) {
        let vector = pendingInterrupts[0]; 
        
        let success = API.generateInterrupt(false, vector); 
        // API.log(`INT: generate 0x${vector.toString(16).toUpperCase()}: success ${success}`);
        
        pendingInterrupts.shift(); 

    }
}

// ============================================================================

API.uiReady = () => {
    terminalConnected = true;
    API.log("UI Connected. Asserting Hardware DTR...");
};

API.receivedFromCustomUi = (msg) => {
    if (msg.command === 'tx') {
        rxQueue.push(msg.char);
        API.log("SIO: Received char 0x" + msg.char.toString(16).toUpperCase() + " from UI.");
        checkInterrupts();
    }
};

API.readPort = (port) => {
    let p = port & 0xFF; 
    if (p === 0x86) {
        let status = terminalConnected ? 0x04 : 0x00; 
        if (rxQueue.length > 0) status |= 0x01; 
        return status; 
    }
    if (p === 0x84) {
        let char = (rxQueue.length > 0) ? rxQueue.shift() : 0x00;
        if (char !== 0x00) API.log("SIO: Z80 Read 0x" + char.toString(16).toUpperCase());
        return char;
    }
    if (p === 0x87) return 0x04; 
    return undefined; 
};

API.writePort = (port, value) => {
    let p = port & 0xFF;
    
    // --- SIO Port A Command (0x86) ---
    if (p === 0x86) {
        if (sioA_PTR === 0) {
            if ((value & 0x38) === 0x28) {
                txA_IntPending = false; // Reset Tx Int Pending Cmd
            }
            sioA_PTR = value & 0x07;
        } else {
            if (sioA_PTR === 1) sioA_WR1 = value;
            sioA_PTR = 0; 
        }
        return;
    }

    // --- SIO Port B Command (0x87) ---
    if (p === 0x87) {
        if (sioB_PTR === 0) {
            sioB_PTR = value & 0x07;
        } else {
            if (sioB_PTR === 1) sioB_WR1 = value;
            if (sioB_PTR === 2) sioB_WR2 = value; 
            sioB_PTR = 0;
        }
        return;
    }

    // --- SIO Port A Data (0x84) ---
    if (p === 0x84) { 
        API.sendToCustomUi({ command: 'con', char: value });
        txA_IntPending = true; // Hardware transmission instantly complete
        return;
    }

    if (p === 0x85) API.sendToCustomUi({ command: 'dbg', char: value });
    if (p === 0x50) API.sendToCustomUi({ command: 'lcd', char: value });
};

// ============================================================================
// Latched Interrupt Drain & Tick Loop
// ============================================================================
//const TSTATES_PER_TICK = 35000; 
const TSTATES_PER_TICK = 350; 
let nextInterruptTstate = TSTATES_PER_TICK;

API.tick = () => {
    checkInterrupts();
    // 4. Evaluate 100Hz CTC Tick
    if (API.tstates >= nextInterruptTstate) {
        nextInterruptTstate += TSTATES_PER_TICK;
        requestInterrupt(0x06, "100Hz CTC Tick"); 
    }
};
import machine
import sys
import select

# Import our custom modules
import display
from pin_map import BACKPLANE_PINS, MUX_ADDR, LOCAL_GPIO_MAP, REMOTE_GPIO_MAP

# ====================================================================
# Hardware Initialization (Multiplexers)
# ====================================================================

rx_pins = {name: machine.Pin(pin_num, machine.Pin.OUT) for name, pin_num in LOCAL_GPIO_MAP.items()}
tx_pins = {name: machine.Pin(pin_num, machine.Pin.OUT) for name, pin_num in REMOTE_GPIO_MAP.items()}

# State variables to track what is currently routed
current_tx_str = "None"
current_rx_str = "None"

def ghost_all():
    """Isolates both the Sender and Receiver cards from the backplane."""
    global current_tx_str, current_rx_str
    
    for i in range(4):
        # 15 (0b1111) is the phantom address that selects nothing
        rx_pins[f"CHIP{i}"].value(1)
        tx_pins[f"CHIP{i}"].value(1)
        
    current_tx_str = "Isolated"
    current_rx_str = "Isolated"

def route_signal(target_pins, mux_addr, channel):
    """Executes a break-before-make routing sequence on a target pin group."""
    # 1. BREAK: Disable the 74LS154 decoder
    for i in range(4):
        target_pins[f"CHIP{i}"].value(1)
        
    # 2. SELECT: Set the multiplexer channel (S0, S1, S2)
    for i in range(3):
        target_pins[f"PORT{i}"].value((channel >> i) & 1)
        
    # 3. MAKE: Enable the specific MUX by writing its address
    for i in range(4):
        target_pins[f"CHIP{i}"].value((mux_addr >> i) & 1)

# Start in a safe, isolated state
ghost_all()

# Boot up the display
display.init()
display.update("BOOTING...", "Initializing MUX...", "Waiting for Serial")

# ====================================================================
# Main Serial Control Loop
# ====================================================================

poll_obj = select.poll()
poll_obj.register(sys.stdin, select.POLLIN)

display.update("READY", f"TX: {current_tx_str}", f"RX: {current_rx_str}")

while True:
    poll_res = poll_obj.poll(10)
    
    if poll_res:
        line = sys.stdin.readline().strip()
        if not line:
            continue
            
        parts = line.upper().split()
        cmd = parts[0]
        
        if cmd == "GHOST":
            ghost_all()
            print("OK GHOST")
            display.update("GHOST MODE", f"TX: {current_tx_str}", f"RX: {current_rx_str}")
            
        elif cmd == "SELECT":
            if len(parts) == 3:
                target = parts[1]  # 'TX' or 'RX'
                pin_str = parts[2]
                
                if target not in ["TX", "RX"]:
                    print("ERR INVALID_TARGET_MUST_BE_TX_OR_RX")
                    continue
                
                # Enforce integer pin values
                try:
                    pin_num = int(pin_str)
                except ValueError:
                    print("ERR PIN_MUST_BE_INTEGER")
                    continue
                
                # Protect power/GND and check mapping
                if pin_num not in BACKPLANE_PINS:
                    print(f"ERR PIN_{pin_num}_UNMAPPED_OR_POWER")
                else:
                    signal_name = BACKPLANE_PINS[pin_num]["signal"]
                    mux_name = BACKPLANE_PINS[pin_num]["mux"]
                    mux_addr = MUX_ADDR[mux_name]
                    channel = BACKPLANE_PINS[pin_num]["channel"]
                    
                    # Route the hardware and update the state string
                    if target == "TX":
                        route_signal(tx_pins, mux_addr, channel)
                        current_tx_str = f"{pin_num} - {signal_name}"
                    else:
                        route_signal(rx_pins, mux_addr, channel)
                        current_rx_str = f"{pin_num} - {signal_name}"
                    
                    # Echo back to laptop
                    print(f"OK {target} {pin_num} {signal_name}")
                    
                    # Update local UI with both tracked states
                    display.update("ROUTING ACTIVE", f"TX: {current_tx_str}", f"RX: {current_rx_str}")
            else:
                print("ERR SYNTAX_SELECT_TX|RX_PIN")
                
        elif cmd == "IDN?":
            print("OK Zx50_PROBE_REVA")
            
        elif cmd == "BRIDGE":
            print("ERR BRIDGE_NOT_IMPLEMENTED_YET")
            
        else:
            print(f"ERR UNKNOWN_COMMAND_{cmd}")
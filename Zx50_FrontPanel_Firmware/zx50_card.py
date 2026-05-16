import time

import pins
from bus_status import BusStatus
from chip_decode import U5Decode, U6Decode


def read_bus():
    # --- Read all bus values through abstracted chip_decode functions ---

    # Latch all cards at the same time
    pins.LE_N(0)
    # These are not latched, so read them first and hope
    # Cast physical pin readings to booleans for our negative logic classes
    wr_n = bool(pins.Z80_WR.value())
    iorq_n = bool(pins.Z80_IORQ.value())

    addr_l = _read_addr_low()
    addr_h = _read_addr_high()
    data_val = _read_z80_data()
    shadow_data_val = _read_shadow_data()

    # These functions return the fully decoded dataclass objects directly!
    u5_decode = _read_u5_status()
    u6_decode = _read_u6_status()

    # Release the latch
    pins.LE_N(1)

    # Instantiate the unified BusStatus object
    # addr_h = 0x23
    # addr_l = 0x45
    # data_val = 0x67
    # shadow_data_val = 0xab
    return BusStatus(wr_n, iorq_n, u5_decode, u6_decode, addr_l, addr_h, data_val, shadow_data_val)

def _read_addr_low():
    pins.OE_U1_ADDR_L.value(0)
    time.sleep_us(10)
    addr_l = pins.read_shared_bus()
    pins.OE_U1_ADDR_L.value(1)
    return addr_l

def _read_addr_high():
    pins.OE_U3_ADDR_H.value(0)
    addr_h = pins.read_shared_bus()
    pins.OE_U3_ADDR_H.value(1)
    return addr_h

def _read_z80_data():
    pins.OE_U4_DATA.value(0)
    data_val = pins.read_shared_bus()
    pins.OE_U4_DATA.value(1)
    return data_val

def _read_u5_status():
    pins.OE_U5_STATUS.value(0)
    status_val = pins.read_shared_bus()
    pins.OE_U5_STATUS.value(1)
    return U5Decode.decode(status_val)

def _read_u6_status():
    pins.OE_U6_SHADOW.value(0)
    shadow_val = pins.read_shared_bus()
    pins.OE_U6_SHADOW.value(1)
    return U6Decode.decode(shadow_val)

def _read_shadow_data():
    pins.OE_U7_SHADOW_DATA.value(0)
    shadow_data_val = pins.read_shared_bus()
    pins.OE_U7_SHADOW_DATA.value(1)
    return shadow_data_val

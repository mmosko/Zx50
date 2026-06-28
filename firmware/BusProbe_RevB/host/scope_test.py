import pyvisa

# Force PyVISA to use the pure-Python 'pyvisa-py' backend
rm = pyvisa.ResourceManager('@py')

# Print available resources to see if the scope is auto-detected
print("Available resources:", rm.list_resources())

try:
    # Attempt connection
    instrument = rm.open_resource("TCPIP::172.16.1.43::INSTR")
    print("Connected successfully!")
    print(instrument.query("*IDN?"))
except Exception as e:
    print(f"Connection failed: {e}")

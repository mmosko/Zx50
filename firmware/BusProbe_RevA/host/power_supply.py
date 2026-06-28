import pyvisa
import time

# Initialize the Resource Manager using the python-vxi11/pyvisa-py backend
rm = pyvisa.ResourceManager('@py')

# Connect to the PSU
# We use ::SOCKET because the SPD3303X VXI-11 implementation is finicky
psu = rm.open_resource('TCPIP0::172.16.1.44::5025::SOCKET')

# CRITICAL: Siglent gear needs the newline termination
psu.read_termination = '\n'
psu.write_termination = '\n'

# Set a reasonable timeout for 40MHz-paced debugging
psu.timeout = 5000

print(f"Connected to: {psu.query('*IDN?')}")

# --- Zx50 Rev A QC Sequence ---

print("Power off CH1")
psu.write("OUTP CH1,OFF")
time.sleep(2)

volts = psu.query("MEAS:VOLT? CH1")
print(f"ch1 volts {volts} V")

# 1. Set Safety overhead
psu.write("CH1:VOLT 5.1")
psu.write("CH1:CURR 1.3")

# 2. Enable Output
print("Power on CH1")
psu.write("OUTP CH1,ON")
time.sleep(1)

volts = psu.query("MEAS:VOLT? CH1")
print(f"ch1 volts {volts} V")


print("Power Rails Active. Monitoring 1.1A target...")

# 3. Log data for your "Medium Run" documentation
for i in range(1, 6):
    current = psu.query("MEAS:CURR? CH1")
    print(f"Sample {i}: {current} A")
    time.sleep(1)

# Restore local control when finished
psu.write("*UNLOCK")
psu.close()
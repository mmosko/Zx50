import machine
import time

# "LED" routes through the CYW43439 wireless chip on the 'W' models
led = machine.Pin("LED", machine.Pin.OUT)

while True:
    led.toggle()
    time.sleep(0.5)

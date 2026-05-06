import serial
import time

ser = serial.Serial('/dev/serial0', 9600, timeout=1)
ser.write(b'HELLO_SELF')
time.sleep(0.1)
res = ser.read(ser.in_waiting)
print(f"Пришло обратно: {res}")
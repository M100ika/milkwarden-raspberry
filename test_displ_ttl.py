import serial, json
s = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
for _ in range(5):
    line = s.readline()
    print(repr(line))
    try: print(json.loads(line))
    except Exception as e: print('ERR:', e)

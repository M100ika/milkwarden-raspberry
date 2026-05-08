import serial                                                                           
s = serial.Serial('/dev/ttyUSB0', 115200, timeout=3)                                    
for _ in range(20):                                                                     
    line = s.readline()                                                               
    if line:                                                                          
        print(line.decode('utf-8', errors='replace').strip()) 
# import sys; sys.path.insert(0, 'src')
# from nextion import NextionDisplay

# d = NextionDisplay('/dev/serial0', 9600, timeout=1.0)
# d.connect()
# d.send('bkcmd=3')

# # Пробуем записать в t0 БЕЗ смены страницы
# d.send('t0.txt="HELLO"')
# resp = d.read_response(timeout=1.0)
# print(d.decode_response(resp))

import serial

ser = serial.Serial('/dev/serial0', 9600, timeout=1)

def send(cmd):
    ser.write(cmd.encode('utf-8'))
    ser.write(b'\xff\xff\xff')  # обязательно!

def update_display(ip, rfid, weight, stall, state):
    # текст
    send(f't0.txt="{ip}"')
    send(f't1.txt="{rfid}"')
    send(f't2.txt="{weight}"')
    send(f't3.txt="{stall:02d}"')  # 01,02,03...
    send(f't6.txt="{"HELLO"}"') 

    # индикатор p0 (показать/скрыть)
    if state:
        send('vis p0,1')
    else:
        send('vis p0,0')

def main():
    ip='192.168.0.10'
    rfid='1234567890'
    weight=12.34
    stall=1
    state=True

    update_display(ip, rfid, weight, stall, state)

if __name__ == '__main__':
    main()
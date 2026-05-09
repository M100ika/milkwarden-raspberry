"""
Диагностика: читает один snap с UART и пишет напрямую в Nextion.
Запуск: python debug_snap.py
"""
import serial
import json
import time

UART_PORT  = "/dev/ttyUSB0"
NX_PORT    = "/dev/serial0"
UART_BAUD  = 115200
NX_BAUD    = 9600
END        = b'\xff\xff\xff'


def nx_send(ser, cmd):
    print(f"  → Nextion: {cmd}")
    ser.write(cmd.encode("ascii") + END)
    ser.flush()
    time.sleep(0.05)


print("=== debug_snap.py ===")

uart = serial.Serial(UART_PORT, UART_BAUD, timeout=3)
nx   = serial.Serial(NX_PORT,   NX_BAUD,   timeout=1)

print(f"UART {UART_PORT} открыт")
print(f"Nextion {NX_PORT} открыт")
print("Жду snap-пакет...")

pkt = None
while pkt is None:
    raw = uart.readline()
    if not raw:
        continue
    try:
        p = json.loads(raw)
    except Exception:
        continue
    if p.get("type") == "snap":
        pkt = p

print(f"Получен snap: id={pkt['id']} weight={pkt['weight']} state={pkt['state']}")
print("Отправляю команды в Nextion...")

nx_send(nx, 't0.txt="LIVE-TEST"')
nx_send(nx, f't1.txt="{pkt.get("rfid") or "---"}"')
nx_send(nx, f't3.txt="{pkt["weight"] / 1000:.2f}"')
nx_send(nx, f't4.txt="{time.strftime("%H:%M:%S", time.localtime(pkt["ts"]))}"')
nx_send(nx, f'vis p0,{1 if pkt["state"] >= 1 else 0}')

print("Готово. Проверь дисплей — должно появиться 'LIVE-TEST' в t0.")
uart.close()
nx.close()

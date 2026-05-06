import sys; sys.path.insert(0, 'src')
from nextion import NextionDisplay

d = NextionDisplay('/dev/serial0', 9600, timeout=1.0)
d.connect()
d.send('bkcmd=3')

# Пробуем записать в t0 БЕЗ смены страницы
d.send('t0.txt="HELLO"')
resp = d.read_response(timeout=1.0)
print(d.decode_response(resp))
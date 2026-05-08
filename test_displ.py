import serial
import time

# Используем /dev/ttyAMA0, так как на RPi 5 это основной аппаратный UART
# Если не заработает, верните /dev/serial0
PORT = '/dev/serial0' 
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)

def send(cmd):
    """Отправляет команду и ждет, пока она уйдет в кабель."""
    full_cmd = cmd.encode('ascii') + b'\xff\xff\xff'
    ser.write(full_cmd)
    ser.flush() # Ждем физического завершения передачи данных
    time.sleep(0.05) # Даем Nextion время обработать команду (важно для RPi 5)

def update_display(ip, rfid, weight, stall, state):
    print(f"Обновление экрана: IP={ip}, Weight={weight}...")
    
    # 1. Принудительно очищаем входной буфер перед отправкой пачки
    ser.reset_input_buffer()

    # 2. Основные данные
    send(f't0.txt="{ip}"')
    send(f't1.txt="{rfid}"')
    send(f't2.txt="{weight}"')
    send(f't3.txt="{stall:02d}"')
    send(f't6.txt="HELLO"') 

    # 3. Состояние видимости
    vis_val = 1 if state else 0
    send(f'vis p0,{vis_val}')
    
    print("Данные отправлены.")

def main():
    # Проверка открытия порта
    if not ser.is_open:
        ser.open()

    ip = '192.168.0.10'
    rfid = '1234567890'
    weight = 12.34
    stall = 1
    state = True

    try:
        update_display(ip, rfid, weight, stall, state)
        
        # Читаем ответ, если он есть (для отладки)
        time.sleep(0.1)
        if ser.in_waiting:
            res = ser.read(ser.in_waiting)
            print(f"Ответ от дисплея (HEX): {res.hex(' ')}")
            
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
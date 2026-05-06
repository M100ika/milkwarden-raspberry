import serial
import time
import os

# Проверяем права доступа
if not os.access('/dev/serial0', os.W_OK):
    print("Ошибка: Нет прав доступа к /dev/serial0. Попробуйте sudo или добавьте пользователя в группу dialout")

def test_raspberry_uart():
    try:
        # Используем /dev/serial0, это универсальный путь для всех версий RPi
        ser = serial.Serial('/dev/serial0', 9600, timeout=1)
        time.sleep(2) # Пауза, чтобы порт "успокоился" после открытия
        
        print("Отправка команд на Nextion через GPIO...")
        
        # Очистка буфера
        ser.write(b'\xff\xff\xff')
        
        # Команды
        cmds = [
            'bkcmd=3',
            'page 0',
            't0.pco=2016', # Зеленый цвет для отличия от теста на ПК
            't0.txt="FROM RPI"',
            't1.txt="GPIO WORKING"',
            'dim=100'
        ]
        
        for cmd in cmds:
            ser.write(cmd.encode('ascii') + b'\xff\xff\xff')
            time.sleep(0.1)
            if ser.in_waiting:
                resp = ser.read(ser.in_waiting)
                print(f"Команда [{cmd}], Ответ: {resp.hex(' ')}")
                
        ser.close()
        print("Тест завершен.")
        
    except Exception as e:
        print(f"Ошибка при работе с UART: {e}")

if __name__ == "__main__":
    test_raspberry_uart()
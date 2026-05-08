import serial
import time

# Настройки порта
PORT = '/dev/serial0'
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)

def send(cmd):
    """Отправка команды с флешем и паузой для стабильности RPi 5"""
    full_cmd = cmd.encode('ascii') + b'\xff\xff\xff'
    ser.write(full_cmd)
    ser.flush()
    time.sleep(0.04) # Микро-пауза для процессора Nextion

def update_section(section_idx, ip, rfid, weight, event_time, state):
    """
    Обновляет одну из 4-х секций на экране.
    section_idx: 1, 2, 3 или 4
    """
    # Маппинг начальных ID для каждой секции
    # Секция 1: t0,  Секция 2: t6,  Секция 3: t12, Секция 4: t18
    base = (section_idx - 1) * 6
    
    print(f"Обновление Секции {section_idx} (базовый ID t{base})...")

    # Текстовые поля (смещение согласно вашей логике)
    send(f't{base}.txt="{ip}"')             # t0, t6, t12, t18
    send(f't{base + 1}.txt="{rfid}"')       # t1, t7, t13, t19
    send(f't{base + 3}.txt="{weight:.2f}"') # t3, t9, t15, t21 (формат 0.00)
    send(f't{base + 4}.txt="{event_time}"') # t4, t10, t16, t22

    # Видимость картинки (p0, p1, p2, p3)
    p_idx = section_idx - 1
    vis_val = 1 if state else 0
    send(f'vis p{p_idx},{vis_val}')

def main():
    try:
        if not ser.is_open:
            ser.open()

        # Тестовые данные для проверки всех секций
        test_data = [
            {"ip": "192.168.0.10", "rfid": "RFID_A1", "weight": 15.50, "time": "10:30", "state": True},
            {"ip": "192.168.0.11", "rfid": "RFID_B2", "weight": 12.05, "time": "10:32", "state": False},
            {"ip": "192.168.0.12", "rfid": "RFID_C3", "weight": 18.20, "time": "10:35", "state": True},
            {"ip": "192.168.0.13", "rfid": "RFID_D4", "weight": 14.10, "time": "10:40", "state": False},
        ]

        # Обновляем каждую секцию по очереди
        for i, data in enumerate(test_data, start=1):
            update_section(i, data["ip"], data["rfid"], data["weight"], data["time"], data["state"])
            time.sleep(0.1) # Небольшая пауза между секциями

        print("\nВсе секции обновлены успешно!")

    except Exception as e:
        print(f"Ошибка при работе с UART: {e}")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
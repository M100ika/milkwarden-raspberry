# Milkwarden Raspberry Pi — CLAUDE.md

## Проект
**Milkwarden Edge** — Python-сервис на Raspberry Pi 5.  
Читает JSON-строки от ESP32 Master по USB (UART0), сохраняет сессионные данные в SQLite
и синхронизирует их на сервер при наличии WiFi.

Суперпроект: `Milkwarden-superproject/raspberry`  
Master ESP32 (поставщик данных): `../integrated/esp32/esp32_master`

## Архитектура системы

```
[4× Slave ESP32] ──ESP-NOW──► [Master ESP32] ──USB/UART──► [Raspberry Pi 5]
                                                                    │
                                                             SQLite (локально)
                                                                    │
                                                       (WiFi) ──► Сервер (будущий)
```

**Nextion NX4827T043 4.3" 480×272** подключён к GPIO14/GPIO15 (UART), но **не входит
в текущую реализацию** — интеграция добавляется отдельно после настройки дисплея.

## Аппаратура

| Интерфейс | Устройство | Порт RPi | Baud |
|-----------|-----------|----------|------|
| USB → Master ESP32 | `/dev/ttyUSB0` (или `ttyACM0`) | USB | 115200 |
| UART (GPIO14/GPIO15) | Nextion Display | `/dev/serial0` | 9600 |

**RPi 5, Raspberry Pi OS Bookworm (64-bit)**

## Стек

- **Язык:** Python 3.11+
- **БД:** SQLite (встроенный `sqlite3`)
- **Сериализация:** `pyserial` — чтение UART
- **HTTP-клиент:** `httpx` (или `requests`) — синхронизация с сервером
- **Планировщик:** `APScheduler` или простой цикл с `time.sleep` — проверка WiFi 5×/день
- **Управление сервисом:** systemd unit

## Входящие данные от ESP32 Master

Каждая строка — JSON, заканчивается `\n`. Поле `type` определяет тип.


## Nextion Integration Protocol (RPi 5 Specifics)

При отправке данных из SnapshotPacket на дисплей строго соблюдать следующие правила:

  1. Терминатор команды: Каждая команда ОБЯЗАТЕЛЬНО заканчивается тремя байтами \xff\xff\xff.

  2. Тайминги (RPi 5): Между каждой командой ser.write() должна быть пауза time.sleep(0.05). Без паузы дисплей переполняет буфер и возвращает ошибку 0x1A.

  3. Принудительный Flush: Использовать ser.flush() после записи, чтобы гарантировать уход данных из системного буфера RPi 5.

  4. Кодировка: Использовать .encode('ascii') для команд. Для кириллицы требуется проверка поддержки шрифтом в Nextion Editor.


## Структура маппинга дисплея (4 секции)
Данные из SnapshotPacket маппятся по ID слава (id 1–4):

  Слой,Описание,Nextion ID (Base = (id-1)*6),Пример (id=1)
  IP,IP адрес slave,t[Base],t0
  RFID,Текущая метка,t[Base + 1],t1
  Weight,Вес (float),t[Base + 3],t3
  Time,Время события,t[Base + 4],t4
  State,Видимость (p0-p3),p[id - 1],p0

### SnapshotPacket (type = "snap") — каждые 500 мс от каждого slave

```json
{"type":"snap","id":1,"rfid":"E20068151234ABCD","beam":0,"state":2,"weight":14250.5,"ts":1746492180}
```

| Поле | Описание |
|------|---------|
| `id` | Номер slave 1–4 |
| `rfid` | EPC hex RFID-метки, `""` если нет |
| `beam` | 0 = луч в норме, 1 = прерван |
| `state` | 0=IDLE, 1=COW_PRESENT, 2=MILKING |
| `weight` | Текущий вес в граммах |
| `ts` | Unix timestamp (UTC+5, Казахстан) |

**Действие RPi:** в текущей реализации — отбросить (Nextion не подключён).  
Когда Nextion будет готов — пересылать на дисплей через `ttyAMA0`.

### SessionPacket (type = "session") — по завершении сессии

```json
{"type":"session","id":1,"rfid":"E20068151234ABCD","w_init":0.0,"w_final":14500.0,"t_start":1746492000,"t_end":1746492300,"reason":0}
```

| Поле | Описание |
|------|---------|
| `id` | Номер slave 1–4 |
| `rfid` | RFID-метка коровы, `""` если не считана |
| `w_init` | Вес в начале сессии (граммы) |
| `w_final` | Вес в конце (граммы) |
| `t_start` | Unix time начала |
| `t_end` | Unix time конца |
| `reason` | 0 = корова ушла, 1 = смена бидона |

**Действие RPi:** сохранить в SQLite с флагом `synced = 0`.

## База данных SQLite

**Файл:** `~/.milkwarden/milkwarden.db` (или `/var/lib/milkwarden/milkwarden.db`)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    esp_id       INTEGER NOT NULL,
    rfid_tag     TEXT    NOT NULL DEFAULT '',
    weight_init  REAL    NOT NULL,
    weight_final REAL    NOT NULL,
    t_start      INTEGER NOT NULL,  -- Unix time
    t_end        INTEGER NOT NULL,  -- Unix time
    end_reason   INTEGER NOT NULL,  -- 0=cow_left 1=bucket_change
    received_at  INTEGER NOT NULL,  -- local Unix time (RPi clock)
    synced       INTEGER NOT NULL DEFAULT 0  -- 0=pending  1=sent_ok
);
```

**Индекс для быстрой выборки несинхронизированных:**
```sql
CREATE INDEX IF NOT EXISTS idx_synced ON sessions (synced);
```

## Логика синхронизации с сервером

### Конфигурационные переменные (в `config.yaml`)

```yaml
server:
  enabled: false            # выключить до появления сервера
  url: "https://example.com/api/sessions"  # заменить когда сервер будет готов
  timeout_sec: 10
  batch_size: 50            # максимум записей за один запрос

sync:
  checks_per_day: 5         # ~каждые 5 часов
```

### Алгоритм синхронизации

```
sync_job():
  if not SERVER_ENABLED:
      return
  if not wifi_connected():
      return
  rows = SELECT * FROM sessions WHERE synced=0 LIMIT batch_size
  if not rows:
      return
  response = POST server_url, json=rows, timeout=timeout_sec
  if response.status == 200:
      ids = [r.id for r in rows]
      DELETE FROM sessions WHERE id IN (ids)
      # или UPDATE sessions SET synced=1 WHERE id IN (ids)
      # и периодически чистить synced=1 старше N дней
  else:
      log error, retry on next scheduled check
```

**Формат POST-запроса на сервер (предлагаемый):**
```json
{
  "device": "milkwarden-edge-01",
  "sessions": [
    {
      "esp_id": 1,
      "rfid_tag": "E20068151234ABCD",
      "weight_init": 0.0,
      "weight_final": 14500.0,
      "t_start": 1746492000,
      "t_end": 1746492300,
      "end_reason": 0,
      "received_at": 1746492310
    }
  ]
}
```

Сервер отвечает `200 OK` → RPi удаляет отправленные строки.  
Любой другой статус / таймаут → данные остаются, следующая попытка через ~5 часов.

## Структура проекта

```
raspberry/
├── CLAUDE.md
├── config/
│   ├── edge.yaml             # основная конфигурация
│   └── secrets.example.yaml  # шаблон для токенов (если появятся)
├── src/
│   ├── main.py               # точка входа, запускает reader + scheduler
│   ├── reader.py             # чтение UART, парсинг JSON строк
│   ├── db.py                 # SQLite: init_db(), save_session(), get_pending(), delete_synced()
│   ├── sync.py               # синхронизация с сервером: sync_job(), wifi_connected()
│   └── config.py             # загрузка edge.yaml
├── services/
│   └── mw-edge.service       # systemd unit
└── docker/
    └── Dockerfile            # опционально
```

## Главный цикл (main.py)

```python
# Запускает два независимых потока:
# 1. reader_loop()  — бесконечный, читает /dev/ttyUSB0 построчно
# 2. sync_scheduler() — раз в (24h / checks_per_day), вызывает sync_job()
```

## reader.py — чтение UART

```python
  # Открывает serial-порт, читает построчно.
  # line → json.loads → если type=="session" → db.save_session()
  # line → json.loads → если type=="snap"    → pass
   
  #   Действие RPi при type=="snap":
  # 1. Извлечь id (1–4).
  # 2. Рассчитать целевые ID компонентов Nextion.
  # 3. Сформировать команды (например, t0.txt="192...").
  # 4. Отправить в /dev/serial0 с соблюдением Nextion Integration Protocol.

  # Обрабатывает JSONDecodeError, serial.SerialException без крашей.
  # При потере порта — переподключение через 5 секунд.
```

## UART-порт

Определяется автоматически или задаётся в конфиге:
```yaml
serial:
  port: "/dev/ttyUSB0"   # или ttyACM0 — зависит от чипа USB-UART на ESP32
  baud: 115200
  timeout_sec: 2
```

Проверить порт на RPi:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
dmesg | tail -20
```

## systemd-сервис

```ini
# /etc/systemd/system/mw-edge.service
[Unit]
Description=Milkwarden Edge
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/milkwarden/raspberry/src/main.py
WorkingDirectory=/home/milkwarden/raspberry
Restart=always
RestartSec=5
User=milkwarden

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable mw-edge
sudo systemctl start mw-edge
journalctl -u mw-edge -f    # логи
```

## Что НЕ реализуется сейчас

| Компонент | Статус | Когда |
|-----------|--------|-------|
| Nextion NX4827T043 | Не реализован | После ручной настройки дисплея |
| Аутентификация сервера | Не реализована | Когда появится сервер |
| SnapshotPacket → хранение | Не нужно | — |

## Зависимости Python

```
pyserial>=3.5
httpx>=0.27
PyYAML>=6.0
APScheduler>=3.10   # или заменить простым time.sleep-циклом
```

Установка:
```bash
pip install pyserial httpx PyYAML APScheduler
```

## Git

Репозиторий: https://github.com/M100ika/milkwarden-integrated  
Ветка: `main`


## Important for AI: 
When writing Nextion code, use serial.Serial('/dev/serial0', 9600). Every command must end with + b'\xff\xff\xff', followed by ser.flush() and time.sleep(0.05). Display has 4 sections; components are t0, t6, t12, t18 (IP), t1, t7... (RFID), t3, t9... (Weight), t4, t10... (Time), and p0-p3 (Visibility).
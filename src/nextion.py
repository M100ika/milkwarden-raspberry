import logging
import time

import serial

log = logging.getLogger(__name__)

_END = b'\xff\xff\xff'

STATE_LABELS = {0: "IDLE", 1: "PRESENT", 2: "MILKING"}

# Nextion return-code map (первый байт ответа)
_RETURN_CODE = {
    0x00: "invalid instruction",
    0x01: "success",
    0x02: "invalid component id",
    0x03: "invalid page id",
    0x1A: "invalid variable",
    0x1C: "assignment failed",
    0x65: "touch event",
    0x66: "current page number",
    0x70: "string data",
    0x71: "numeric data",
    0x86: "enter sleep",
    0x87: "exit sleep",
    0x88: "ready",
}


class NextionDisplay:
    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout: float = 1.0,
        components: dict | None = None,
    ):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._ser: serial.Serial | None = None
        self._components: dict = components or {
            "ip":     "t0",
            "rfid":   "t1",
            "weight": "t2",
            "stall":  "t3",
            "state":  "p0",
        }

    def connect(self) -> bool:
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=self._timeout)
            time.sleep(0.1)
            self._ser.reset_input_buffer()
            log.info("Nextion connected: %s @ %d", self._port, self._baud)
            return True
        except serial.SerialException as e:
            log.error("Nextion connect failed: %s", e)
            return False

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
            log.info("Nextion disconnected")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    def send(self, cmd: str) -> None:
        if not self._ser or not self._ser.is_open:
            raise RuntimeError("Nextion not connected")
        self._ser.write(cmd.encode("ascii") + _END)
        log.debug("→ %s", cmd)

    def read_response(self, timeout: float = 0.5) -> bytes | None:
        if not self._ser or not self._ser.is_open:
            return None
        self._ser.timeout = timeout
        buf = b''
        while True:
            chunk = self._ser.read(64)
            if not chunk:
                break
            buf += chunk
            if b'\xff\xff\xff' in buf:
                break
        return buf if buf else None

    def decode_response(self, raw: bytes) -> str:
        if not raw:
            return "<no response>"
        code = raw[0]
        label = _RETURN_CODE.get(code, f"unknown(0x{code:02x})")
        return f"0x{code:02x} [{label}] raw={raw.hex()}"

    def set_text(self, component: str, text: str) -> None:
        self.send(f'{component}.txt="{text}"')

    def set_val(self, component: str, value: int) -> None:
        self.send(f'{component}.val={value}')

    def set_page(self, page: int | str) -> None:
        self.send(f'page {page}')

    def set_visible(self, component: str, visible: bool) -> None:
        self.send(f'vis {component},{1 if visible else 0}')

    def set_backlight(self, brightness: int) -> None:
        """Яркость 0–100."""
        self.send(f'dim={brightness}')

    def update_display(
        self,
        *,
        stall: int,
        ip: str,
        rfid: str,
        weight: str,
        state: bool,
    ) -> None:
        c = self._components
        self.set_text(c["ip"], ip or "---")
        self.set_text(c["rfid"], rfid[:16] if rfid else "---")
        self.set_text(c["weight"], weight)
        self.set_text(c["stall"], f"{stall:02d}")
        self.set_visible(c["state"], state)

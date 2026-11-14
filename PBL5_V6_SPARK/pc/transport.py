"""Serial worker reconnects automatically and never logs outgoing secret frames."""
from __future__ import annotations
import queue
import threading
import time
import uuid
from protocol import encode_command, parse_snapshot

class SerialWorker(threading.Thread):
    def __init__(self, port: str, events: queue.Queue, outbound: queue.Queue, stop: threading.Event):
        super().__init__(daemon=True)
        self.port, self.events, self.outbound, self.stop = port, events, outbound, stop

    def run(self) -> None:
        try:
            import serial
        except ImportError:
            self.events.put(('notice', 'Chua co pyserial. Cai requirements-wifi.txt.'))
            return
        while not self.stop.is_set():
            connection_id = uuid.uuid4().hex
            client_id = uuid.uuid4().hex
            connection = None
            try:
                connection = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=1, rtscts=False, dsrdtr=False)
                connection.dtr = False; connection.rts = False
                connection.port = self.port; connection.open()
                self.events.put(('opened', connection_id, client_id))
                buffer = b''; last_valid = time.monotonic()
                while not self.stop.is_set():
                    for _ in range(8):
                        try: dest, command = self.outbound.get_nowait()
                        except queue.Empty: break
                        if dest != connection_id: continue
                        packet = encode_command(command)
                        if connection.write(packet) != len(packet): raise OSError('short_serial_write')
                    buffer += connection.read(min(connection.in_waiting or 1, 4096))
                    while b'\n' in buffer:
                        raw, buffer = buffer.split(b'\n', 1)
                        line = raw.decode('utf-8', errors='replace').strip()
                        snapshot = parse_snapshot(line)
                        if snapshot:
                            last_valid = time.monotonic()
                            self.events.put(('snapshot', connection_id, snapshot, time.monotonic()))
                        elif 'RFID_PYTHON_' in line or 'RFID_MULTI_STORE_V5' in line:
                            self.events.put(('notice', 'Firmware cu: can nap PBL5_UNIFIED_V6; khong tron V4/V5.'))
                        elif line == 'waiting for download':
                            self.events.put(('notice', 'ESP32 dang o bootloader. Nha BOOT va nhan EN/RESET.'))
                    if len(buffer) > 8192: buffer = b''
                    if time.monotonic() - last_valid > 10: raise OSError('serial_heartbeat_timeout')
            except (OSError, ValueError):
                self.events.put(('closed', connection_id))
                self.events.put(('notice', f'Khong giu duoc {self.port}. Dong Serial Monitor; dang thu lai.'))
            finally:
                if connection is not None: connection.close()
            self.stop.wait(2)

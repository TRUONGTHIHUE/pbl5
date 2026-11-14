"""Pure application controller; no Tk, camera, HTTP or serial dependencies.

All mutations run on the UI thread. Async workers return the original Job stamp;
old jobs cannot change a new card, a reset board, or a recovered Wi-Fi session.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import ipaddress
from typing import Any
from backend import BackendError, validate_store_result
from protocol import normalize_rfid, valid_text

@dataclass(frozen=True)
class Job:
    kind: str
    stamp: tuple
    payload: dict = field(repr=False)

class Controller:
    def __init__(self):
        self.connection_id = self.client_id = self.boot_id = ''
        self.generation: int | None = None
        self.uid = ''
        self.epoch = 0
        self.link_epoch = 0
        self.store: dict | None = None
        self.wifi_credentials: dict = {}
        self.wifi: dict = {}
        self.ready = False
        self.phase = 'disconnected'
        self.status = 'Cho ket noi USB.'
        self.product: dict | None = None
        self.commands: list[tuple[str, dict]] = []
        self.jobs: list[Job] = []
        self.resolve_job: Job | None = None
        self.product_job: Job | None = None
        self.resolve_deadline = self.product_deadline = 0.0
        self.last_snapshot = self.last_poll = self.last_hello = 0.0
        self.attempted_key: tuple | None = None
        self.request_number = 0

    @property
    def key(self) -> tuple:
        return self.connection_id, self.client_id, self.boot_id, self.generation, self.uid, self.epoch

    @property
    def camera_stamp(self) -> tuple | None:
        return (*self.key, self.link_epoch) if self.ready else None

    def clear_selection(self) -> None:
        self.epoch += 1
        self.link_epoch += 1
        self.store = None
        self.wifi_credentials.clear()
        self.product = self.product_job = self.resolve_job = None
        self.ready = False
        self.attempted_key = None

    def opened(self, connection_id: str, client_id: str, now: float) -> None:
        self.clear_selection()
        self.commands.clear(); self.jobs.clear()
        self.connection_id, self.client_id = connection_id, client_id
        self.boot_id = ''; self.generation = None; self.uid = ''; self.wifi = {}
        self.last_snapshot = self.last_poll = self.last_hello = now
        self.phase = 'handshake'; self.status = 'Da mo USB. Dang xac nhan firmware V6...'
        self.send('hello')

    def disconnected(self, connection_id: str) -> None:
        if connection_id != self.connection_id: return
        self.clear_selection(); self.commands.clear(); self.jobs.clear()
        self.connection_id = self.boot_id = ''; self.generation = None; self.uid = ''; self.wifi = {}
        self.phase = 'disconnected'; self.status = 'Mat USB. Dang thu mo lai; ket qua cu da bi huy.'

    def send(self, command: str, **fields) -> None:
        if not self.connection_id: return
        data = {'command': command, 'client_id': self.client_id}
        if command not in ('hello', 'status'):
            if not self.boot_id or self.generation is None: return
            data.update(boot_id=self.boot_id, generation=self.generation)
        data.update(fields)
        self.commands.append((self.connection_id, data))

    def snapshot(self, connection_id: str, data: dict, now: float) -> None:
        if connection_id != self.connection_id: return
        self.last_snapshot = now
        if data.get('client_id') != self.client_id:
            if self.ready or self.store or self.boot_id:
                self.clear_selection(); self.boot_id = ''; self.generation = None
            self.phase = 'handshake'; self.status = 'Dong bo lai ESP32; cho hello.'
            if now - self.last_hello >= 1:
                self.send('hello'); self.last_hello = now
            return
        boot, gen, uid = data['boot_id'], data['generation'], data['rfid_uid']
        if boot == self.boot_id and self.generation is not None and gen < self.generation:
            return
        new_key = (boot, gen, uid) != (self.boot_id, self.generation, self.uid)
        if new_key:
            self.clear_selection()
            self.boot_id, self.generation, self.uid = boot, gen, uid
            self.status = 'Dang xac thuc thiet bi va tim cua hang...'
        self.phase = data['phase']
        previous_link_seq = self.wifi.get('link_seq')
        self.wifi = dict(data['wifi'])
        if self.ready and previous_link_seq is not None and self.wifi.get('link_seq') != previous_link_seq:
            self.link_epoch += 1; self.product = self.product_job = None
        # Recover even if a complete disconnect/reconnect was missed by the GUI,
        # or a snapshot arrived after a temporary heartbeat gap.
        if uid and not self.store and not self.resolve_job and self.attempted_key is None and self.phase in ('ready', 'connecting', 'reconnecting', 'wifi_failed'):
            self.attempted_key = self.key
            self.send('retry')
        if self.phase == 'waiting_credentials' and uid and self.attempted_key != self.key:
            self.attempted_key = self.key
            self.resolve_job = Job('resolve', self.key, {'uid': uid})
            self.resolve_deadline = now + 23
            self.jobs.append(self.resolve_job)
        try:
            ip_ok = not ipaddress.IPv4Address(self.wifi.get('ip', '')).is_unspecified
        except (ipaddress.AddressValueError, TypeError):
            ip_ok = False
        can_use = bool(self.store and data.get('ready') is True and self.wifi.get('connected') is True and
                       data.get('store_id') == self.store['id'] and
                       self.wifi.get('ssid') == self.wifi_credentials.get('ssid') and ip_ok)
        if self.ready and not can_use:
            self.link_epoch += 1; self.product = self.product_job = None
        self.ready = can_use
        if can_use:
            if self.product_job is None and self.product is None:
                action = self.wifi.get('action')
                self.status = 'SAN SANG: dung cua hang, Wi-Fi co IP. ' + ('Da giu ket noi chung.' if action == 'reused' else 'Co the quet barcode.')
        elif self.phase in ('connecting', 'switching', 'reconnecting'):
            self.status = 'ESP32 dang ket noi/ket noi lai Wi-Fi; tam dung barcode.'
        elif self.phase == 'wifi_failed':
            self.status = 'Ket noi Wi-Fi that bai. Kiem tra SSID/pass that; ESP32 se thu lai. Khong dung cua hang cu.'
        elif self.phase == 'credentials_timeout':
            self.resolve_job = None; self.store = None; self.wifi_credentials.clear()
            self.status = 'Het thoi gian cap Wi-Fi. Kiem tra backend va nhan Quet lai.'
        elif self.phase == 'backend_error' and not self.status.startswith('LOI BACKEND'):
            self.status = 'Backend tu choi hoac timeout. Kiem tra cau hinh va Quet lai.'
        elif self.phase == 'idle':
            self.status = 'USB san sang. Quet the RFID.'

    def resolved(self, job: Job, result: dict, now: float) -> bool:
        if job != self.resolve_job or job.stamp != self.key: return False
        try:
            validate_store_result(result, self.uid)
        except BackendError as error:
            self.failed(job, error.code); return False
        self.resolve_job = None
        self.store = dict(result['store'])
        self.wifi_credentials = dict(result['wifi'])
        self.send('wifi', rfid_uid=self.uid, store_id=self.store['id'], store_name=self.store['name'],
                  owner_uid=self.store['owner_uid'], ssid=self.wifi_credentials['ssid'], password=self.wifi_credentials['password'])
        self.status = 'Da lay cau hinh cua hang, da gui qua USB; cho ESP32 bao IP.'
        return True

    def failed(self, job: Job, code: str) -> bool:
        if job.kind == 'resolve':
            if job != self.resolve_job or job.stamp != self.key: return False
            self.resolve_job = None; self.store = None; self.wifi_credentials.clear()
            self.ready = False; self.product = self.product_job = None
            self.send('cancel')
            self.status = 'LOI BACKEND: ' + code + '. Kiem tra cau hinh va nhan Quet lai.'
            return True
        if job != self.product_job or job.stamp != self.camera_stamp: return False
        self.product_job = None; self.product = None
        if code in ('store_not_authorized', 'device_not_authenticated'):
            self.ready = False; self.link_epoch += 1; self.store = None; self.wifi_credentials.clear()
            self.send('cancel')
        self.status = 'LOI TRA SAN PHAM: ' + code + '. Khong hien ket qua cu.'
        return True

    def barcode(self, barcode: Any, stamp: tuple | None, now: float) -> bool:
        if not self.ready or stamp != self.camera_stamp or self.product_job or not valid_text(barcode, 128): return False
        self.request_number += 1
        self.product = None
        self.product_job = Job('product', self.camera_stamp, {'store_id': self.store['id'], 'barcode': barcode, 'request_id': self.request_number})
        self.product_deadline = now + 23
        self.jobs.append(self.product_job)
        self.status = 'Dang tra barcode trong cua hang da chon...'
        return True

    def product_result(self, job: Job, result: dict) -> bool:
        if job != self.product_job or not self.ready or job.stamp != self.camera_stamp: return False
        if result.get('store_id') != self.store['id'] or result.get('barcode') != job.payload['barcode'] or result.get('status') not in ('found', 'not_found', 'duplicate') or not isinstance(result.get('fields'), dict):
            return self.failed(job, 'backend_product_identity_mismatch')
        self.product_job = None; self.product = result
        self.status = {'found': 'Da tim thay san pham dung cua hang.', 'not_found': 'Khong co barcode trong cua hang nay.', 'duplicate': 'LOI DU LIEU: barcode trung trong cua hang nay.'}[result['status']]
        return True

    def retry(self) -> None:
        self.send('retry')
        self.clear_selection()
        self.status = 'Da yeu cau quet lai/cap lai cau hinh.'

    def tick(self, now: float) -> None:
        if not self.connection_id: return
        if self.phase == 'handshake' and now - self.last_hello >= 1:
            self.send('hello'); self.last_hello = now
        if now - self.last_poll >= 2:
            self.send('status'); self.last_poll = now
        if self.resolve_job and now >= self.resolve_deadline:
            self.failed(self.resolve_job, 'resolve_timeout')
        if self.product_job and now >= self.product_deadline:
            self.failed(self.product_job, 'product_timeout')
        if now - self.last_snapshot > 7:
            if self.ready or self.store:
                self.clear_selection()
            self.phase = 'handshake'
            self.status = 'Khong co phan hoi V6. Kiem tra firmware, USB va BOOT/EN.'

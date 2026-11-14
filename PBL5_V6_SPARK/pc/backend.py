"""HTTPS device-auth client. No Firebase owner accounts or Admin SDK on scanner PC."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from protocol import normalize_rfid, valid_text, valid_wifi

class BackendError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(f'HTTP {status}: {code}' if status else code)

@dataclass(frozen=True)
class DeviceConfig:
    endpoint: str
    device_id: str
    device_token: str = field(repr=False)
    project_id: str = 'quanlycuahang-afb59'
    timeout_seconds: float = 15
    allow_localhost: bool = False

    @classmethod
    def load(cls, path: str | Path) -> 'DeviceConfig':
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise BackendError('device_config_missing_or_invalid_run_provision_device') from None
        try:
            config = cls(**data)
        except TypeError:
            raise BackendError('device_config_fields_invalid') from None
        config.validate()
        return config

    def validate(self) -> None:
        if not isinstance(self.endpoint, str): raise BackendError('invalid_endpoint')
        if 'REPLACE_' in self.endpoint or str(self.device_token).startswith('REPLACE_'):
            raise BackendError('device_config_not_provisioned')
        parsed = urllib.parse.urlparse(self.endpoint)
        local = self.allow_localhost is True and parsed.hostname in ('127.0.0.1', 'localhost', '::1') and parsed.scheme == 'http'
        if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or (parsed.scheme != 'https' and not local):
            raise BackendError('endpoint_must_be_https')
        if not isinstance(self.device_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', self.device_id):
            raise BackendError('invalid_device_id')
        if not isinstance(self.device_token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', self.device_token):
            raise BackendError('invalid_device_token')
        if not isinstance(self.timeout_seconds, (int, float)) or not 1 <= self.timeout_seconds <= 20:
            raise BackendError('invalid_timeout')
        if not isinstance(self.project_id, str) or not self.project_id:
            raise BackendError('missing_project_id')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a device token to a redirected URL.
        return None

class Backend:
    def __init__(self, config: DeviceConfig):
        config.validate()
        self.config = config
        self._verified = False
        self._verify_lock = threading.Lock()

    def request(self, action: str, **fields) -> dict:
        body = json.dumps({'api_version': 2, 'action': action, **fields}, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.config.endpoint, data=body, method='POST', headers={
            'Content-Type': 'application/json', 'X-Device-Id': self.config.device_id,
            'Authorization': 'Bearer ' + self.config.device_token})
        opener = urllib.request.build_opener(NoRedirect())
        try:
            with opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(65537)
                if len(raw) > 65536: raise BackendError('backend_response_too_large')
                result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            code = 'backend_http_error'
            try:
                value = json.loads(exc.read(4096)).get('code')
                if isinstance(value, str) and re.fullmatch(r'[a-z0-9_]{1,80}', value): code = value
            except (ValueError, TypeError, AttributeError): pass
            raise BackendError(code, exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise BackendError('backend_network_or_tls_error') from None
        except (ValueError, UnicodeError):
            raise BackendError('backend_invalid_json') from None
        if not isinstance(result, dict) or result.get('ok') is not True or result.get('api_version') != 2:
            raise BackendError('backend_protocol_mismatch')
        return result

    def ping(self) -> dict:
        result = self.request('ping')
        if result.get('service') != 'pbl5-device-api' or result.get('device_id') != self.config.device_id or result.get('project_id') != self.config.project_id:
            raise BackendError('backend_project_or_device_mismatch')
        self._verified = True
        return result

    def verify(self) -> None:
        with self._verify_lock:
            if not self._verified: self.ping()

    def resolve(self, uid: str) -> dict:
        self.verify()
        canonical = normalize_rfid(uid)
        if not canonical: raise BackendError('invalid_rfid')
        result = self.request('resolve_store', rfid_uid=canonical)
        validate_store_result(result, canonical)
        return result

    def product(self, store_id: str, barcode: str) -> dict:
        self.verify()
        if not valid_text(barcode, 128): raise BackendError('invalid_barcode')
        result = self.request('lookup_product', store_id=store_id, barcode=barcode)
        if result.get('store_id') != store_id or result.get('barcode') != barcode or result.get('status') not in ('found', 'not_found', 'duplicate') or not isinstance(result.get('fields'), dict):
            raise BackendError('backend_product_identity_mismatch')
        return result

def validate_store_result(result: dict, uid: str) -> None:
    store, wifi = result.get('store'), result.get('wifi')
    if not isinstance(store, dict) or not isinstance(wifi, dict): raise BackendError('backend_store_invalid')
    sid = store.get('id')
    if not valid_text(sid, 255) or '/' in sid or sid in ('.', '..') or not valid_text(store.get('name'), 255) or not valid_text(store.get('owner_uid'), 128) or store.get('rfid_uid') != uid or not valid_wifi(wifi.get('ssid'), wifi.get('password')):
        raise BackendError('backend_store_invalid')

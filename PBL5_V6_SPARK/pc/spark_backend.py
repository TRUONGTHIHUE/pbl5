"""Spark REST adapter. Firebase Auth scanner account + Security Rules, no Admin key.
Firestore paths are explicit: rfidStores/{UID} -> stores/{id} -> products query.
All network calls in an operation share a 20 second deadline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from backend import BackendError, NoRedirect, validate_store_result
from protocol import normalize_rfid, valid_text

@dataclass(frozen=True)
class SparkConfig:
    api_key: str = field(repr=False)
    email: str = field(repr=False)
    password: str = field(repr=False)
    scanner_uid: str
    project_id: str = 'quanlycuahang-afb59'
    timeout_seconds: float = 10

    @classmethod
    def load(cls, path):
        try:
            cfg = cls(**json.loads(Path(path).read_text(encoding='utf-8')))
            cfg.validate()
            return cfg
        except (OSError, ValueError, TypeError):
            raise BackendError('spark_config_missing_or_invalid_run_provision_spark') from None

    def validate(self):
        if not all(isinstance(x, str) and x for x in (self.api_key, self.email, self.password, self.scanner_uid, self.project_id)):
            raise ValueError('missing_fields')
        if '/' in self.scanner_uid or not valid_text(self.scanner_uid, 128):
            raise ValueError('invalid_scanner_uid')
        if not all(c.isalnum() or c == '-' for c in self.project_id):
            raise ValueError('invalid_project')
        if not isinstance(self.timeout_seconds, (int, float)) or not 1 <= self.timeout_seconds <= 15:
            raise ValueError('invalid_timeout')

def unpack(value):
    for key in ('stringValue', 'timestampValue', 'referenceValue', 'booleanValue', 'doubleValue'):
        if key in value: return value[key]
    if 'integerValue' in value: return int(value['integerValue'])
    if 'nullValue' in value: return None
    if 'mapValue' in value: return fields(value['mapValue'])
    if 'arrayValue' in value: return [unpack(v) for v in value['arrayValue'].get('values', [])]
    if 'geoPointValue' in value: return value['geoPointValue']
    return None

def fields(document):
    return {k: unpack(v) for k, v in document.get('fields', {}).items()}

class SparkBackend:
    def __init__(self, config):
        config.validate()
        self.config = config
        self._token = ''
        self._expires = 0
        self._lock = threading.Lock()
        self._local = threading.local()
        self._base = 'https://firestore.googleapis.com/v1/projects/' + config.project_id + '/databases/(default)/documents/'

    def _begin(self): self._local.deadline = time.monotonic() + 20

    def _remaining(self):
        remaining = self._local.deadline - time.monotonic()
        if remaining <= 0: raise BackendError('backend_operation_timeout')
        return remaining

    def _http(self, url, body=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        raw = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=raw, headers=headers, method='GET' if body is None else 'POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=min(self.config.timeout_seconds, self._remaining())) as response:
                data = response.read(65537)
                if len(data) > 65536: raise BackendError('backend_response_too_large')
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            # Do not expose Auth response/body or credentials in exception messages.
            code = {400:'firebase_invalid_request_or_credentials', 401:'device_not_authenticated',
                    403:'store_not_authorized', 404:'firebase_document_not_found', 429:'firebase_quota_or_rate_limit'}.get(exc.code, 'firebase_http_error')
            raise BackendError(code, exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise BackendError('backend_network_or_tls_error') from None
        except (ValueError, UnicodeError):
            raise BackendError('backend_invalid_json') from None

    def _login(self):
        if not self._lock.acquire(timeout=self._remaining()): raise BackendError('backend_operation_timeout')
        try:
            if self._token and time.monotonic() < self._expires: return self._token
            response = self._http('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + urllib.parse.quote(self.config.api_key, safe=''),
                                  {'email':self.config.email, 'password':self.config.password, 'returnSecureToken':True})
            if not isinstance(response, dict) or response.get('localId') != self.config.scanner_uid:
                raise BackendError('scanner_uid_mismatch')
            token = response.get('idToken')
            if not isinstance(token, str) or not token: raise BackendError('device_not_authenticated')
            try: lifetime = min(3600, max(1, int(response.get('expiresIn', 3600))))
            except (ValueError, TypeError): raise BackendError('backend_invalid_json') from None
            self._token = token
            self._expires = time.monotonic() + max(0, lifetime - 60)
            return token
        finally: self._lock.release()

    def _get(self, path):
        document = self._http(self._base + '/'.join(urllib.parse.quote(part, safe='') for part in path), token=self._login())
        if not isinstance(document, dict) or not isinstance(document.get('fields'), dict): raise BackendError('backend_invalid_document')
        return fields(document)

    def _check_device(self):
        device = self._get(['devices', self.config.scanner_uid])
        if device.get('enabled') is not True: raise BackendError('device_not_authenticated')

    def ping(self):
        self._begin(); self._check_device()
        return {'ok':True, 'service':'pbl5-spark-firestore', 'device_id':self.config.scanner_uid, 'project_id':self.config.project_id}

    def resolve(self, uid):
        self._begin()
        canonical = normalize_rfid(uid)
        if not canonical: raise BackendError('invalid_rfid')
        self._check_device()
        try: mapping = self._get(['rfidStores', canonical])
        except BackendError as e:
            if e.status == 404: raise BackendError('store_not_found') from None
            raise
        sid = mapping.get('storeId')
        if not valid_text(sid,255) or '/' in sid or sid in ('.','..'): raise BackendError('invalid_rfid_mapping')
        data = self._get(['stores', sid])
        if data.get('enabled') is False: raise BackendError('store_not_authorized')
        # Canonical storage is required; never silently select mismatched RFID.
        if data.get('rfidId') != canonical: raise BackendError('rfid_mapping_store_mismatch')
        result = {'ok':True,'store':{'id':sid,'name':data.get('storeName'),'owner_uid':data.get('ownerUid'),'rfid_uid':canonical},
                  'wifi':{'ssid':data.get('wifiSSID'),'password':data.get('wifiPassword')}}
        validate_store_result(result,canonical)
        return result

    def product(self, store_id, barcode):
        self._begin()
        if not valid_text(store_id,255) or '/' in store_id or store_id in ('.','..') or not valid_text(barcode,128): raise BackendError('invalid_product_query')
        self._check_device()
        result = self._http(self._base+'stores/'+urllib.parse.quote(store_id,safe='')+':runQuery',
            {'structuredQuery':{'from':[{'collectionId':'products'}],
             'where':{'fieldFilter':{'field':{'fieldPath':'barcode'},'op':'EQUAL','value':{'stringValue':barcode}}}, 'limit':2}}, token=self._login())
        if not isinstance(result,list): raise BackendError('backend_invalid_json')
        documents = [row['document'] for row in result if isinstance(row,dict) and 'document' in row]
        status = 'not_found' if not documents else 'duplicate' if len(documents)>1 else 'found'
        payload = fields(documents[0]) if status=='found' else {}
        return {'ok':True,'store_id':store_id,'barcode':barcode,'status':status,'fields':payload}

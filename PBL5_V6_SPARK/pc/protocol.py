"""Protocol v2: every session is keyed by client, boot, generation and RFID."""
from __future__ import annotations
import json
import re
from typing import Any

PROTOCOL_VERSION = 2
MAX_LINE = 2048

def normalize_rfid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = re.sub(r'[\s:-]', '', value).upper()
    return value if re.fullmatch(r'(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})', value) else None

def valid_text(value: Any, max_bytes: int, empty: bool = False) -> bool:
    return isinstance(value, str) and (empty or bool(value)) and len(value.encode('utf-8')) <= max_bytes and not re.search(r'[\x00-\x1f\x7f]', value)

def valid_wifi(ssid: Any, password: Any) -> bool:
    return bool(valid_text(ssid, 32) and isinstance(password, str) and
                (password == '' or re.fullmatch(r'[\x20-\x7e]{8,63}', password) or re.fullmatch(r'[0-9a-fA-F]{64}', password)))

def encode_command(command: dict) -> bytes:
    raw = ('@CMD:' + json.dumps({'v': PROTOCOL_VERSION, **command}, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    if len(raw) > MAX_LINE:
        raise ValueError('serial_command_too_large')
    return raw

def parse_snapshot(line: str) -> dict | None:
    if not line.startswith('@STATE:'):
        return None
    try:
        data = json.loads(line[7:])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get('v') != PROTOCOL_VERSION:
        return None
    if not isinstance(data.get('boot_id'), str) or not re.fullmatch(r'[a-fA-F0-9]{16}', data['boot_id']):
        return None
    client = data.get('client_id')
    if not isinstance(client, str) or (client and not re.fullmatch(r'[a-fA-F0-9]{32}', client)):
        return None
    gen = data.get('generation')
    if type(gen) is not int or not 0 <= gen <= 0xFFFFFFFF:
        return None
    if not isinstance(data.get('wifi'), dict) or type(data.get('ready')) is not bool:
        return None
    uid = data.get('rfid_uid')
    if not isinstance(uid, str) or (uid and normalize_rfid(uid) != uid):
        return None
    if not valid_text(data.get('phase'), 48):
        return None
    return data

"""Generate a scanner credential ONCE. This does NOT write to Firestore."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
from backend import DeviceConfig, BackendError

def create_config(device_id: str, endpoint: str, project_id: str, output: Path) -> str:
    config = DeviceConfig(endpoint=endpoint.rstrip('/'), device_id=device_id,
                          device_token=secrets.token_urlsafe(32), project_id=project_id)
    config.validate()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(asdict(config), stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return hashlib.sha256(config.device_token.encode()).hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--device-id', default='may-quet-01')
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--project', default='quanlycuahang-afb59')
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('device_config.json'))
    args = parser.parse_args()
    try:
        digest = create_config(args.device_id, args.endpoint, args.project, args.output)
    except FileExistsError:
        raise SystemExit('Da co file cau hinh. Khong ghi de token. Xem huong dan doi endpoint/thu hoi token.') from None
    except (BackendError, OSError):
        raise SystemExit('Khong tao duoc cau hinh. Kiem tra endpoint HTTPS, device ID va quyen ghi file.') from None
    print('DA TAO:', args.output)
    print('Firestore devices/' + args.device_id)
    print('  enabled (boolean): true')
    print('  tokenSha256 (string):', digest)
    print('Them stores/STORE_ID/authorizedDevices/' + args.device_id + ' -> enabled=true')
    print('Khong chia se device_config.json. Token goc KHONG duoc in ra terminal.')

if __name__ == '__main__': main()

"""Create a local device secret ONCE. Never upload device_config.json.
Example:
 python provision_device.py --device-id may-quet-01 --endpoint https://REGION-PROJECT.cloudfunctions.net/deviceApi
"""
import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse


def create_config(device_id, endpoint, output):
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', device_id):
        raise ValueError('device_id phai 3-64 ky tu a-z A-Z 0-9 - _')
    url = urlparse(endpoint)
    if url.scheme != 'https' or not url.netloc or url.username or url.password:
        raise ValueError('Endpoint phai la HTTPS URL cua Firebase function')
    token = secrets.token_urlsafe(32)
    document = {'endpoint': endpoint.rstrip('/'), 'device_id': device_id, 'device_token': token}
    output.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL prevents accidental replacement/lockout of an existing device.
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(document, file, indent=2, ensure_ascii=False)
            file.write('\n')
    except Exception:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Tao token thiet bi (mot lan).')
    parser.add_argument('--device-id', required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--output', default=str(Path(__file__).with_name('device_config.json')))
    args = parser.parse_args()
    try:
        token_hash = create_config(args.device_id, args.endpoint, Path(args.output))
    except FileExistsError:
        raise SystemExit('Da co device_config.json. Khong tao lai! Xem README de cap quyen.') from None
    except (ValueError, OSError) as exc:
        raise SystemExit(f'Loi: {exc}') from None
    print('DA TAO file:', args.output)
    print('VAO FIRESTORE CONSOLE -> devices / ' + args.device_id)
    print('Them enabled (boolean) = true')
    print('Them tokenSha256 (string) = ' + token_hash)
    print('Token goc da luu TRONG file device_config.json; KHONG chia se file do.')
    print('Sau do cap quyen cho moi cua hang:')
    print('stores/{storeId}/authorizedDevices/' + args.device_id + ' -> enabled=true')


if __name__ == '__main__':
    main()

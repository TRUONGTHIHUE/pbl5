import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pc'))
import provision_device
import rfid_barcode


class FakeHTTP:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode('utf-8')
    def __enter__(self):
        return io.BytesIO(self.payload)
    def __exit__(self, *args):
        return False


class DeviceTests(unittest.TestCase):
    def test_provision_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'device_config.json'
            result = provision_device.create_config('pc-test-01', 'https://example.cloudfunctions.net/deviceApi', p)
            self.assertEqual(len(result), 64)
            cfg = rfid_barcode.read_device_config(p)
            self.assertEqual(cfg['device_id'], 'pc-test-01')
            self.assertNotEqual(cfg['device_token'], result)
            with self.assertRaises(FileExistsError):
                provision_device.create_config('pc-test-01', 'https://example.cloudfunctions.net/deviceApi', p)

    def test_authenticated_resolve(self):
        cfg = {'endpoint': 'https://example.cloudfunctions.net/deviceApi',
               'device_id': 'pc-test-01', 'device_token': 'A' * 43}
        result = {'ok': True, 'store_id': 'shop-a', 'store_name': 'Cua hang A',
                  'ssid': 'WiFi_A', 'password': 'PasswordA123'}
        def open_(_, timeout=0):
            self.assertGreater(timeout, 0)
            self.assertEqual(_.get_header('X-device-id'), 'pc-test-01')
            self.assertTrue(_.get_header('Authorization').startswith('Bearer '))
            raw = json.loads(_.data)
            self.assertEqual(raw['rfid_uid'], 'C79A0C03')
            return FakeHTTP(result)
        with patch('urllib.request.urlopen', new=open_):
            self.assertEqual(rfid_barcode.retrieve_wifi_from_backend('c7:9a:0c:03', cfg)[0], 'shop-a')

if __name__ == '__main__':
    unittest.main()

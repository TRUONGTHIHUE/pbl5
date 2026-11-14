"""Real local HTTP between Python client and Node API, with in-memory fake Firestore."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pc'))
from backend import Backend, BackendError, DeviceConfig

@unittest.skipUnless(shutil.which('node'),'Node is required for local cross-language integration')
class HttpIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script=Path(__file__).resolve().parents[1]/'functions'/'tests'/'mock_http.js'
        cls.process=subprocess.Popen(['node',str(script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=json.loads(cls.process.stdout.readline())
        cls.endpoint='http://127.0.0.1:'+str(ready['port'])
        cls.client=Backend(DeviceConfig(cls.endpoint,'scanner-test','SIMULATED_DEVICE_TOKEN_FOR_UNIT_TESTS_123456789','test-project',allow_localhost=True))
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.communicate(timeout=5)
    def test_ping_and_normalized_rfid(self):
        self.assertEqual(self.client.ping()['project_id'],'test-project')
        self.assertEqual(self.client.resolve('CD 4B 1E 03')['store']['id'],'shop-a')
    def test_two_stores_same_wifi_and_same_barcode(self):
        a=self.client.resolve('CD4B1E03');b=self.client.resolve('C79A0C03')
        self.assertEqual(a['wifi'],b['wifi'])
        pa=self.client.product(a['store']['id'],'00123456')
        pb=self.client.product(b['store']['id'],'00123456')
        self.assertEqual(pa['fields']['name'],'Only Shop A')
        self.assertEqual(pb['fields']['name'],'Only Shop B')
        self.assertEqual(pa['barcode'],'00123456')
    def test_missing_card_and_product(self):
        with self.assertRaises(BackendError) as cm:self.client.resolve('DEADBEEF')
        self.assertEqual(cm.exception.code,'store_not_found')
        self.assertEqual(self.client.product('shop-a','99999')['status'],'not_found')
    def test_wrong_device_token_rejected(self):
        client=Backend(DeviceConfig(self.endpoint,'scanner-test','WRONG_SIMULATED_TOKEN_1234567890123456','test-project',allow_localhost=True))
        with self.assertRaises(BackendError) as cm:client.ping()
        self.assertEqual(cm.exception.status,401)
    def test_project_mismatch_is_rejected(self):
        client=Backend(DeviceConfig(self.endpoint,'scanner-test','SIMULATED_DEVICE_TOKEN_FOR_UNIT_TESTS_123456789','different-project',allow_localhost=True))
        with self.assertRaises(BackendError) as cm:client.ping()
        self.assertEqual(cm.exception.code,'backend_project_or_device_mismatch')

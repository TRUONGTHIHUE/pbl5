import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pc'))
from provision_device import create_config
from backend import DeviceConfig
from camera import decode_barcodes

class ProvisionTests(unittest.TestCase):
    def test_generate_once_and_hash_without_owner_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'device_config.json'
            digest=create_config('scanner-test','https://example.invalid/deviceApiV6','test-project',path)
            config=DeviceConfig.load(path)
            self.assertEqual(hashlib.sha256(config.device_token.encode()).hexdigest(),digest)
            self.assertNotIn('email',json.loads(path.read_text()))
            self.assertNotIn(config.device_token,repr(config))
            with self.assertRaises(FileExistsError):create_config('scanner-test','https://example.invalid/deviceApiV6','test-project',path)

class CameraLogicTests(unittest.TestCase):
    def test_fake_model_and_decoder_keep_leading_zero(self):
        # Tests app processing with synthetic pixels/fake detector/decoder, NOT a camera or YOLO model.
        import numpy as np
        class CV:
            COLOR_BGR2GRAY=1
            def cvtColor(self,a,_):return a[:,:,0]
            def rectangle(self,*_):pass
        class Model:
            def predict(self,*_,**__):return [types.SimpleNamespace(boxes=[])]
        def fake_decode(_):return [types.SimpleNamespace(data=b'00123456'),types.SimpleNamespace(data=b'\xff')]
        _, values=decode_barcodes(np.zeros((20,30,3),dtype=np.uint8),Model(),fake_decode,CV())
        self.assertEqual(values,{'00123456'})

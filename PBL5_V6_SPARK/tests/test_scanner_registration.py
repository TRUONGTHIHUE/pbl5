import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pc'))
from register_scanner import register
from spark_backend import SparkConfig

class RegistrationTests(unittest.TestCase):
    def test_signup_writes_config_once_and_does_not_grant_permissions(self):
        requests=[]
        class Opener:
            def open(self,request,timeout):
                requests.append(request)
                payload=json.loads(request.data)
                assert payload['returnSecureToken'] is True
                return io.BytesIO(b'{"localId":"scanner-test-uid"}')
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'spark_config.json'
            cfg={'project_id':'quanlycuahang-afb59','api_key':'fake-api','email':'scanner@example.invalid','password':'FAKE_PASSWORD_123'}
            uid=register(cfg,output,Opener())
            self.assertEqual(uid,'scanner-test-uid')
            self.assertEqual(SparkConfig.load(output).scanner_uid,uid)
            self.assertEqual(len(requests),1)
            self.assertIn('accounts:signUp',requests[0].full_url)
            with self.assertRaises(FileExistsError):register(cfg,output,Opener())
            self.assertEqual(len(requests),1)
    def test_bad_config_does_not_register_account(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):register({'api_key':'','email':'x','password':'x'},Path(temp)/'x.json')
if __name__=='__main__':unittest.main()

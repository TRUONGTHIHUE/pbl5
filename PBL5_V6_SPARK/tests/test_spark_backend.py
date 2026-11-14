import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pc'))
from spark_backend import SparkConfig,SparkBackend,unpack
from backend import BackendError

class Fake(SparkBackend):
    def __init__(self):
        super().__init__(SparkConfig(api_key='fake',email='scanner@example.invalid',password='fake-password',scanner_uid='scanner1'))
        self.authorized=True;self.device=True;self.calls=[];self.duplicate=False
        self.docs={
            'devices/scanner1':{'enabled':True},
            'rfidStores/C79A0C03':{'storeId':'a'},'rfidStores/11223344':{'storeId':'b'},
            'stores/a':{'storeName':'A','ownerUid':'ownerA','rfidId':'C79A0C03','wifiSSID':'SameWifi','wifiPassword':'password123'},
            'stores/b':{'storeName':'B','ownerUid':'ownerB','rfidId':'11223344','wifiSSID':'SameWifi','wifiPassword':'password123'}}
    def _http(self,url,body=None,token=None):
        self.calls.append((url,body,token))
        if 'signInWithPassword' in url:return {'localId':'scanner1','idToken':'fake-id-token','expiresIn':'3600'}
        if not self.authorized and '/devices/' not in url:raise BackendError('store_not_authorized',403)
        if ':runQuery' in url:
            self.assert_query=body
            if body['structuredQuery']['where']['fieldFilter']['value']['stringValue']=='missing':return [{'readTime':'now'}]
            value='ProductA' if '/stores/a:' in url else 'ProductB'
            doc={'document':{'fields':{'barcode':{'stringValue':'00123'},'name':{'stringValue':value}}}}
            return [doc,doc] if self.duplicate else [doc]
        path=url.split('/documents/',1)[1]
        if path not in self.docs:raise BackendError('firebase_document_not_found',404)
        d=dict(self.docs[path])
        if path=='devices/scanner1':d['enabled']=self.device
        return {'fields':{k:({'booleanValue':v} if isinstance(v,bool) else {'stringValue':v}) for k,v in d.items()}}

class SparkTests(unittest.TestCase):
    def test_flow_same_wifi_two_stores_same_barcode(self):
        b=Fake();self.assertTrue(b.ping()['ok'])
        a=b.resolve('c7:9a:0c:03');c=b.resolve('11223344')
        self.assertEqual(a['wifi'],c['wifi']);self.assertNotEqual(a['store']['id'],c['store']['id'])
        self.assertEqual(b.product('a','00123')['fields']['name'],'ProductA')
        self.assertEqual(b.product('b','00123')['fields']['name'],'ProductB')
        self.assertEqual(b.assert_query['structuredQuery']['where']['fieldFilter']['value'],{'stringValue':'00123'})
        self.assertEqual(sum('signInWithPassword' in c[0] for c in b.calls),1)
    def test_missing_duplicate(self):
        b=Fake();self.assertEqual(b.product('a','missing')['status'],'not_found')
        b.duplicate=True;self.assertEqual(b.product('a','00123')['status'],'duplicate')
    def test_mapping_must_match_store(self):
        b=Fake();b.docs['rfidStores/C79A0C03']['storeId']='b'
        with self.assertRaisesRegex(BackendError,'rfid_mapping_store_mismatch'):b.resolve('C79A0C03')
    def test_revoked_permission_and_device(self):
        b=Fake();b.authorized=False
        with self.assertRaises(BackendError):b.resolve('C79A0C03')
        with self.assertRaises(BackendError):b.product('a','00123')
        b.device=False
        with self.assertRaisesRegex(BackendError,'device_not_authenticated'):b.ping()
    def test_bad_uid_numeric_barcode_and_path(self):
        b=Fake()
        for uid in ['email@example.invalid','123']:
            with self.assertRaises(BackendError):b.resolve(uid)
        for sid,code in [('a',123),('../other','00123')]:
            with self.assertRaises(BackendError):b.product(sid,code)
    def test_account_mismatch(self):
        b=Fake();b.config=SparkConfig(api_key='fake',email='fake',password='fake',scanner_uid='wrong')
        with self.assertRaisesRegex(BackendError,'scanner_uid_mismatch'):b.ping()
    def test_typed_values_and_config_redacts_secret(self):
        self.assertEqual(unpack({'arrayValue':{'values':[{'integerValue':'42'},{'stringValue':'00123'}]}}),[42,'00123'])
        self.assertNotIn('fake-password',repr(Fake().config))
    def test_missing_mapping_does_not_guess_store(self):
        with self.assertRaisesRegex(BackendError,'store_not_found'):Fake().resolve('AABBCCDD')
    def test_expired_token_reauthenticates(self):
        b=Fake();b.ping();b._expires=0;b.ping()
        self.assertEqual(sum('signInWithPassword' in c[0] for c in b.calls),2)

if __name__=='__main__':unittest.main()

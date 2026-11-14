import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'pc'))
from controller import Controller
from protocol import parse_snapshot, encode_command, normalize_rfid
from backend import DeviceConfig, BackendError
import json

CLIENT='a'*32
BOOT='1'*16

def snapshot(gen=1, uid='CD4B1E03', phase='waiting_credentials', sid='', ready=False,
             client=CLIENT, boot=BOOT, seq=0, ssid='TEST_NETWORK', ip='192.168.1.2'):
    return {'v':2, 'firmware':'PBL5_UNIFIED_V6','boot_id':boot,'client_id':client,
            'generation':gen,'rfid_uid':uid,'store_id':sid,'phase':phase,'ready':ready,
            'wifi':{'connected':ready,'ssid':ssid if ready else '', 'ip':ip if ready else '',
                    'action':'reused', 'reason':0,'link_seq':seq}}

def result(sid='shop-a', uid='CD4B1E03', owner='owner-a'):
    return {'ok':True,'api_version':2,'store':{'id':sid,'name':'Shop '+sid,'owner_uid':owner,'rfid_uid':uid},
            'wifi':{'ssid':'TEST_NETWORK','password':'TEST_PASSWORD_123'}}

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.c=Controller();self.c.opened('usb1',CLIENT,0)
    def resolve_a(self):
        self.c.snapshot('usb1',snapshot(),1)
        job=self.c.resolve_job
        self.assertTrue(self.c.resolved(job,result(),2))
        self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True,seq=1),3)
        self.assertTrue(self.c.ready)
        return job
    def test_full_store_wifi_product_flow(self):
        self.resolve_a()
        self.assertTrue(self.c.barcode('00123456',self.c.camera_stamp,4))
        job=self.c.product_job
        self.assertTrue(self.c.product_result(job,{'store_id':'shop-a','barcode':'00123456','status':'found','fields':{'name':'A','barcode':'00123456'}}))
        self.assertEqual(self.c.product['fields']['barcode'],'00123456')
    def test_card_change_during_resolve_discards_old_credentials(self):
        self.c.snapshot('usb1',snapshot(),1);old=self.c.resolve_job
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03'),2)
        before=len(self.c.commands)
        self.assertFalse(self.c.resolved(old,result(),3))
        self.assertEqual(len(self.c.commands),before)
        self.assertIsNone(self.c.store)
        self.assertTrue(self.c.resolved(self.c.resolve_job,result('shop-b','C79A0C03','owner-b'),4))
    def test_old_product_cannot_override_new_store(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4);old=self.c.product_job
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03'),5)
        self.assertFalse(self.c.product_result(old,{'store_id':'shop-a','barcode':'00123456','status':'found','fields':{'name':'A'}}))
        self.assertIsNone(self.c.product)
    def test_same_ssid_does_not_identify_store(self):
        self.resolve_a();self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03'),4)
        self.c.resolved(self.c.resolve_job,result('shop-b','C79A0C03','owner-b'),5)
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03',phase='ready',sid='shop-a',ready=True),6)
        self.assertFalse(self.c.ready)
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03',phase='ready',sid='shop-b',ready=True),7)
        self.assertTrue(self.c.ready);self.assertEqual(self.c.store['id'],'shop-b')
    def test_wrong_password_status_blocks_products(self):
        self.c.snapshot('usb1',snapshot(),1);self.c.resolved(self.c.resolve_job,result(),2)
        self.c.snapshot('usb1',snapshot(phase='wifi_failed',sid='shop-a'),3)
        self.assertFalse(self.c.ready);self.assertFalse(self.c.barcode('00123456',None,4))
    def test_wifi_loss_and_reconnect_invalidate_inflight_product(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4);old=self.c.product_job
        self.c.snapshot('usb1',snapshot(phase='reconnecting',sid='shop-a',seq=2),5)
        self.assertFalse(self.c.ready);self.assertIsNone(self.c.product_job)
        self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True,seq=3),6)
        self.assertTrue(self.c.ready)
        self.assertFalse(self.c.product_result(old,{'store_id':'shop-a','barcode':'00123456','status':'found','fields':{}}))
    def test_fast_disconnect_reconnect_link_sequence_invalidates_product(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4);old=self.c.product_job
        self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True,seq=3),5)
        self.assertTrue(self.c.ready);self.assertIsNone(self.c.product_job)
        self.assertFalse(self.c.product_result(old,{}))
    def test_serial_loss_discards_all_pending_work(self):
        self.c.snapshot('usb1',snapshot(),1);old=self.c.resolve_job
        self.c.disconnected('usb1')
        self.assertFalse(self.c.resolved(old,result(),3));self.assertIsNone(self.c.store)
    def test_board_reset_same_generation_not_same_session(self):
        self.c.snapshot('usb1',snapshot(),1);old=self.c.resolve_job
        self.c.snapshot('usb1',snapshot(boot='2'*16),2)
        self.assertFalse(self.c.resolved(old,result(),3))
    def test_reopening_python_requires_fresh_backend_authorization(self):
        self.c.snapshot('usb1',snapshot(client='b'*32,phase='ready',sid='shop-a',ready=True),2)
        self.assertFalse(self.c.ready);self.assertIsNone(self.c.store)
        self.c.snapshot('usb1',snapshot(gen=2),3)
        self.assertIsNotNone(self.c.resolve_job)
        self.assertEqual(self.c.resolve_job.payload['uid'],'CD4B1E03')
    def test_backend_errors_clear_store_and_send_cancel(self):
        self.c.snapshot('usb1',snapshot(),1);job=self.c.resolve_job
        self.c.failed(job,'store_not_authorized')
        self.assertIsNone(self.c.store);self.assertFalse(self.c.ready)
        self.assertEqual(self.c.commands[-1][1]['command'],'cancel')
    def test_resolve_timeout_rejects_late_result(self):
        self.c.snapshot('usb1',snapshot(),1);job=self.c.resolve_job
        self.c.tick(25)
        self.assertFalse(self.c.resolved(job,result(),26))
    def test_product_timeout_rejects_late_result(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4);job=self.c.product_job
        self.c.tick(28)
        self.assertFalse(self.c.product_result(job,{}));self.assertIsNone(self.c.product)
    def test_missing_duplicate_and_numeric_barcode(self):
        self.resolve_a()
        self.assertFalse(self.c.barcode(123,self.c.camera_stamp,4))
        for status in ('not_found','duplicate'):
            self.c.barcode('00123456',self.c.camera_stamp,4)
            self.c.product_result(self.c.product_job,{'store_id':'shop-a','barcode':'00123456','status':status,'fields':{}})
            self.assertEqual(self.c.product['status'],status)
    def test_wrong_store_product_response_is_rejected(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4)
        self.c.product_result(self.c.product_job,{'store_id':'shop-b','barcode':'00123456','status':'found','fields':{}})
        self.assertIsNone(self.c.product)
    def test_revoked_permission_blocks_further_scans(self):
        self.resolve_a();self.c.barcode('00123456',self.c.camera_stamp,4)
        self.c.failed(self.c.product_job,'store_not_authorized')
        self.assertFalse(self.c.ready);self.assertIsNone(self.c.store)
    def test_stale_camera_frame_after_new_card_is_ignored(self):
        self.resolve_a();stamp=self.c.camera_stamp
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03'),4)
        self.c.resolved(self.c.resolve_job,result('shop-b','C79A0C03','owner-b'),5)
        self.c.snapshot('usb1',snapshot(gen=2,uid='C79A0C03',phase='ready',sid='shop-b',ready=True),6)
        self.assertFalse(self.c.barcode('00123456',stamp,7))
    def test_no_duplicate_backend_job_for_repeated_status(self):
        for t in range(1,5):self.c.snapshot('usb1',snapshot(),t)
        self.assertEqual(len(self.c.jobs),1)
    def test_ip_alone_and_wrong_ssid_not_ready(self):
        self.c.snapshot('usb1',snapshot(),1);self.c.resolved(self.c.resolve_job,result(),2)
        for changes in ({'ssid':'OTHER'},{'ip':'0.0.0.0'},{'ip':''}):
            self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True,**changes),3)
            self.assertFalse(self.c.ready)
    def test_heartbeat_gap_recovers_by_requesting_new_generation(self):
        self.resolve_a();self.c.tick(12)
        self.assertFalse(self.c.ready)
        self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True,seq=1),13)
        self.assertEqual(self.c.commands[-1][1]['command'],'retry')
    def test_snapshot_without_seen_scan_requests_fresh_resolve(self):
        self.c.snapshot('usb1',snapshot(phase='ready',sid='shop-a',ready=True),1)
        self.assertFalse(self.c.ready);self.assertEqual(self.c.commands[-1][1]['command'],'retry')

class ProtocolTests(unittest.TestCase):
    def test_protocol_and_normalization(self):
        data=snapshot()
        self.assertIsNotNone(parse_snapshot('@STATE:'+json.dumps(data)))
        self.assertIsNone(parse_snapshot('@STORE:'+json.dumps(data)))
        self.assertIsNone(parse_snapshot('@STATE:{"v":1}'))
        self.assertEqual(normalize_rfid('CD 4B 1E 03'),'CD4B1E03')
        self.assertEqual(normalize_rfid('c7:9a:0c:03'),'C79A0C03')
    def test_encode_boundary_and_string_barcode(self):
        self.assertTrue(encode_command({'command':'status'}).endswith(b'\n'))
        with self.assertRaises(ValueError):encode_command({'huge':'x'*3000})
    def test_config_validation_and_secret_repr(self):
        token='SIMULATED_TOKEN_FOR_TESTS_ONLY_123456789'
        c=DeviceConfig('https://example.invalid/deviceApiV6','scanner-test',token)
        c.validate();self.assertNotIn(token,repr(c))
        with self.assertRaises(BackendError):DeviceConfig('http://example.com','scanner-test',token).validate()
        DeviceConfig('http://127.0.0.1:9000','scanner-test',token,allow_localhost=True).validate()

if __name__=='__main__':unittest.main()

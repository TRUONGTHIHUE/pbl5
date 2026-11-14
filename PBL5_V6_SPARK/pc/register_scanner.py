"""Register a scanner Auth user on the USER's PC; never grants itself Firestore rights.
Creates Auth user only when operator confirms; existing configs are not overwritten.
"""
from __future__ import annotations
from dataclasses import asdict
from getpass import getpass
import json
import os
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse
from backend import NoRedirect, BackendError
from spark_backend import SparkConfig

def register(config_fields, output: Path, opener=None):
    if output.exists(): raise FileExistsError('spark_config_exists')
    # Validate all known fields before creating a remote account.
    temporary = SparkConfig(scanner_uid='registration_pending', **config_fields)
    temporary.validate()
    req = urllib.request.Request('https://identitytoolkit.googleapis.com/v1/accounts:signUp?key='+urllib.parse.quote(temporary.api_key,safe=''),
        data=json.dumps({'email':temporary.email,'password':temporary.password,'returnSecureToken':True}).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    try:
        with (opener or urllib.request.build_opener(NoRedirect())).open(req,timeout=15) as response:
            result=json.loads(response.read(65536))
    except urllib.error.HTTPError as exc:
        code='registration_failed'
        try:
            message=json.loads(exc.read(4096)).get('error',{}).get('message','')
            for known in ('EMAIL_EXISTS','OPERATION_NOT_ALLOWED','INVALID_EMAIL','WEAK_PASSWORD','TOO_MANY_ATTEMPTS_TRY_LATER','CONFIGURATION_NOT_FOUND'):
                if isinstance(message,str) and message.startswith(known):code=known;break
        except (ValueError,AttributeError):pass
        raise BackendError(code,exc.code) from None
    except (OSError,ValueError,urllib.error.URLError):
        raise BackendError('registration_network_or_response_error_check_auth_users_before_retry') from None
    uid=result.get('localId') if isinstance(result,dict) else None
    if not isinstance(uid,str) or not uid:raise BackendError('registration_response_invalid')
    config=SparkConfig(scanner_uid=uid,**config_fields);config.validate()
    # Auth creation and local write cannot be atomic. On write failure recover the UID in Console.
    try:
        output.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(str(output),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(asdict(config),f,ensure_ascii=False,indent=2)
    except OSError:
        raise BackendError('auth_user_created_but_config_not_saved_use_provision_spark') from None
    return uid

def main():
    output=Path(__file__).with_name('spark_config.json')
    if output.exists():raise SystemExit('Da co spark_config.json: khong dang ky lai. Chay app.py --test-backend.')
    print('TAO TAI KHOAN FIREBASE AUTH RIENG CHO MAY QUET. KHONG DUNG EMAIL CHU CUA HANG.')
    print('Can bat Email/Password trong Firebase Authentication truoc. Khong can Blaze.')
    data={'project_id':input('Project ID [quanlycuahang-afb59]: ').strip() or 'quanlycuahang-afb59',
          'api_key':input('Web API Key cua project: ').strip(),
          'email':input('Email RIENG cho may quet (ban quan ly): ').strip()}
    password=getpass('Mat khau MOI cho tai khoan may quet: ')
    if password!=getpass('Nhap lai mat khau: '):raise SystemExit('Hai mat khau khong khop. Chua tao tai khoan.')
    data['password']=password
    print('Se tao Auth user va luu cau hinh tren may nay, KHONG tao quyen Firestore.')
    if input('Nhap DANGKY de xac nhan: ').strip()!='DANGKY':raise SystemExit('Da huy.')
    try:uid=register(data,output)
    except (BackendError,ValueError,FileExistsError) as e:
        raise SystemExit(str(e)+'. Neu EMAIL_EXISTS: dung pc/provision_spark.py voi UID da co trong Authentication -> Users.') from None
    print('DA TAO. UID MAY QUET:',uid)
    print('Admin tao trong Firestore Console: devices/'+uid+' -> enabled (boolean): true')
    print('Moi cua hang: stores/STORE_ID/authorizedDevices/'+uid+' -> enabled (boolean): true')
    print('Mapping: rfidStores/UID_THE -> storeId (string): STORE_ID')
    print('Doi chieu Rules theo BAT_DAU_SPARK.md. Tai khoan moi chua doc duoc du lieu cho den khi duoc cap quyen.')
    print('Khong chia se pc/spark_config.json.')
if __name__=='__main__':main()

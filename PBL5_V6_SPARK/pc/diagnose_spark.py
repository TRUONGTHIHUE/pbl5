"""Read-only diagnosis. Never prints API key, email, password, ID/refresh tokens.
No registration, writes, Rules changes or device grants are performed.
"""
import base64
import json
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse
from backend import NoRedirect, BackendError
from spark_backend import SparkConfig


def redact(text, secrets):
    value=str(text)
    for secret in sorted((x for x in secrets if isinstance(x,str) and x),key=len,reverse=True):
        value=value.replace(secret,'[HIDDEN]')
    return value[:1500]


def request_json(stage,url,secrets,data=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,data=None if data is None else json.dumps(data).encode(),headers=headers,
                               method='GET' if data is None else 'POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(65537)
            if len(raw)>65536:
                print(stage+': response_too_large');return None
            result=json.loads(raw)
            print(stage+': HTTP '+str(response.status))
            return result
    except urllib.error.HTTPError as exc:
        print(stage+': HTTP '+str(exc.code))
        try:
            body=json.loads(exc.read(16384));error=body.get('error',{})
            if isinstance(error,dict):
                print('FIREBASE_STATUS:',redact(error.get('status',''),secrets))
                print('FIREBASE_MESSAGE:',redact(error.get('message',''),secrets))
        except (ValueError,AttributeError):print('Non-JSON Firebase/proxy response; no body printed.')
    except (urllib.error.URLError,OSError,ValueError):
        print(stage+': network_tls_or_response_error')
    return None


def main():
    try:cfg=SparkConfig.load(Path(__file__).with_name('spark_config.json'))
    except BackendError as error:raise SystemExit(str(error)) from None
    secrets=[cfg.api_key,cfg.email,cfg.password]
    print('PROJECT_CONFIG:',cfg.project_id)
    print('SCANNER_UID_CONFIG:',cfg.scanner_uid)
    auth=request_json('AUTH','https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key='+urllib.parse.quote(cfg.api_key,safe=''),secrets,
                      {'email':cfg.email,'password':cfg.password,'returnSecureToken':True})
    if not isinstance(auth,dict):return
    for key in ('idToken','refreshToken'):secrets.append(auth.get(key,''))
    uid=auth.get('localId');token=auth.get('idToken')
    print('SCANNER_UID_AUTH:',uid)
    if uid!=cfg.scanner_uid or not isinstance(token,str):
        print('STOP: scanner_uid_mismatch_or_missing_token');return
    try:
        payload=token.split('.')[1];claims=json.loads(base64.urlsafe_b64decode(payload+'='*((-len(payload))%4)))
        # Informational only. Firestore validates the real token; no local auth bypass.
        print('TOKEN_PROJECT:',claims.get('aud','unknown'))
        if claims.get('aud')!=cfg.project_id:print('PROJECT_MISMATCH: API key/Auth account belongs to another Firebase project.')
    except (ValueError,IndexError,TypeError):print('TOKEN_PROJECT: unable_to_inspect')
    url='https://firestore.googleapis.com/v1/projects/'+cfg.project_id+'/databases/(default)/documents/devices/'+urllib.parse.quote(uid,safe='')
    print('DEVICE_PATH: devices/'+uid)
    document=request_json('GET_DEVICE',url,secrets,token=token)
    if isinstance(document,dict):
        enabled=document.get('fields',{}).get('enabled',{})
        print('ENABLED_IS_BOOLEAN_TRUE:',enabled.get('booleanValue') is True)
        print('DEVICE_READ_OK: use app.py --test-backend next.')
    print('No password or token printed. No Firebase data changed.')

if __name__=='__main__':main()

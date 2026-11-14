"""Interactive scanner Auth config; no account-owner password, no service account."""
from dataclasses import asdict
from getpass import getpass
import json
import os
from pathlib import Path
from spark_backend import SparkConfig

def main():
    output=Path(__file__).with_name('spark_config.json')
    if output.exists(): raise SystemExit('Da co pc/spark_config.json. Khong ghi de. Sua file tren may neu can.')
    print('Nhap tai khoan Firebase Authentication RIENG cho may quet; KHONG dung tai khoan chu cua hang.')
    cfg=SparkConfig(project_id=input('Project ID [quanlycuahang-afb59]: ').strip() or 'quanlycuahang-afb59',
                    api_key=input('Web API Key cua Firebase project: ').strip(),
                    scanner_uid=input('UID tai khoan may quet (Authentication -> Users): ').strip(),
                    email=input('Email tai khoan may quet: ').strip(),
                    password=getpass('Mat khau tai khoan may quet (an khi nhap): '))
    cfg.validate()
    fd=os.open(str(output),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(asdict(cfg),f,ensure_ascii=False,indent=2)
    print('Da tao',output,'; khong chia se file nay.')
    print('Tao devices/'+cfg.scanner_uid+' -> enabled (boolean)=true trong Console.')
    print('Moi cua hang: authorizedDevices/'+cfg.scanner_uid+' -> enabled=true.')
if __name__=='__main__': main()

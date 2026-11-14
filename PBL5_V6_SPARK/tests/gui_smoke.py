"""Tk smoke test with FAKE backend/USB. Run: xvfb-run -a python tests/gui_smoke.py"""
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pc'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from app import DesktopApp
from test_controller import snapshot, result, CLIENT

class FakeBackend:
    def resolve(self,uid):return result()
    def product(self,store_id,barcode):return {'ok':True,'api_version':2,'store_id':store_id,'barcode':barcode,'status':'found','fields':{'name':'Simulated product','barcode':barcode}}
root=tk.Tk()
app=DesktopApp(root,FakeBackend(),'TEST',Path('no-model-needed'),0,True,start_workers=False)
threading.Thread(target=app.network_worker,daemon=True).start()
app.events.put(('opened','usb1',CLIENT))
current=snapshot()
commands=[]
errors=[]
submitted=False

def fake_usb():
    global current,submitted
    if app.closed:return
    try:
        while True:
            _,cmd=app.outbound.get_nowait();commands.append(cmd)
            if cmd['command']=='wifi':
                current=snapshot(phase='ready',sid='shop-a',ready=True,seq=1)
            app.events.put(('snapshot','usb1',current))
    except queue.Empty:pass
    if app.controller.ready and not submitted:
        submitted=True
        app.manual.insert(0,'00123456');app.submit_manual()
    root.after(30,fake_usb)

def check():
    try:
        assert app.controller.ready
        assert app.controller.product['fields']['barcode']=='00123456'
        assert '00123456' in app.details.get('1.0','end')
        assert 'Reuse:' in app.vars['wifi'].get() and 'Switch:' in app.vars['wifi'].get()
        assert app.secret_entry.cget('show')=='*'
        assert app.vars['password'].get()=='TEST_PASSWORD_123'
        app.show_secret.set(True);app.toggle_secret();assert app.secret_entry.cget('show')==''
        app.hide_secret();assert app.secret_entry.cget('show')=='*'
        assert any(c['command']=='wifi' and c['owner_uid']=='owner-a' for c in commands)
        try:
            from PIL import ImageGrab
            image=ImageGrab.grab()
            image.save(str(Path(__file__).resolve().parents[1]/'evidence'/'gui_mock.png'))
        except Exception:pass
    except BaseException as exc:errors.append(exc)
    finally:app.close()
root.after(10,fake_usb)
root.after(1500,check)
root.mainloop()
if errors:raise errors[0]
print('PASS Tk GUI + fake USB/backend + manual barcode + masked/reveal control.')
print('This is a simulation, NOT ESP32/camera/live-Firebase validation.')

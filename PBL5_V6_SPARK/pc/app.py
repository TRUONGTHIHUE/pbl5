"""Single supported desktop entry point: app.py [--wifi-only] --port COM4."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import queue
import threading
import time
from backend import Backend, BackendError, DeviceConfig
from controller import Controller, Job
from transport import SerialWorker

ROOT = Path(__file__).resolve().parent.parent

class DesktopApp:
    def __init__(self, root, backend: Backend, port: str, model: Path, camera: int, wifi_only: bool,
                 start_workers: bool = True, speech: bool = True):
        import tkinter as tk
        from tkinter import ttk, scrolledtext
        self.root, self.backend = root, backend
        self.controller = Controller()
        self.stop = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.outbound: queue.Queue = queue.Queue(maxsize=64)
        self.network_jobs: queue.LifoQueue = queue.LifoQueue(maxsize=16)
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.shared_lock = threading.Lock()
        self.shared_stamp = None
        self.shared_key = None
        self.closed = False
        self.last_spoken_state = None
        self.last_spoken_product = None
        self.speaker = None
        self.blocked: set[str] = set()
        self.seen_at: dict[str, float] = {}
        self.last_camera_stamp = None
        self.last_identity = None
        self.last_product_text = ''
        self.photo = None
        self.vars = {k: tk.StringVar(root, '') for k in ('status','rfid','store','owner','ssid','password','wifi','notice')}
        self.show_secret = tk.BooleanVar(root, False)
        root.title('PBL5 UNIFIED V6 - RFID / Wi-Fi / Barcode')
        root.geometry('1120x780'); root.minsize(900, 620)
        top = ttk.Frame(root, padding=12); top.pack(fill='both', expand=True)
        top.columnconfigure(0, weight=1); top.columnconfigure(1, weight=1); top.rowconfigure(8, weight=1)
        ttk.Label(top, text='PBL5 - RFID / WI-FI / BARCODE', font=('Segoe UI', 14, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=6)
        info = ttk.Frame(top); info.grid(row=1, column=0, sticky='nsew', padx=(0, 12))
        info.columnconfigure(1, weight=1)
        for i, (key, label) in enumerate([('rfid','RFID'),('store','Cua hang'),('owner','Chu cua hang'),('ssid','SSID tu Firebase'),('password','Mat khau Wi-Fi'),('wifi','Ket noi ESP32')]):
            ttk.Label(info, text=label+':').grid(row=i, column=0, sticky='nw', pady=4, padx=(0,8))
            if key == 'password':
                self.secret_entry = ttk.Entry(info, textvariable=self.vars[key], state='readonly', show='*')
                self.secret_entry.grid(row=i, column=1, sticky='ew')
            else:
                ttk.Label(info, textvariable=self.vars[key], wraplength=365).grid(row=i, column=1, sticky='w', pady=4)
        self.reveal_button = ttk.Checkbutton(info, text='Hien mat khau 15 giay (khong chup/chia se)', variable=self.show_secret, command=self.toggle_secret)
        self.reveal_button.grid(row=6, column=0, columnspan=2, sticky='w', pady=5)
        self.preview = ttk.Label(top, text='Camera preview\n--wifi-only: khong mo camera', anchor='center')
        self.preview.grid(row=1, column=1, rowspan=4, sticky='nsew')
        ttk.Label(top, textvariable=self.vars['status'], wraplength=520, font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=10)
        controls = ttk.Frame(top); controls.grid(row=3, column=0, sticky='ew')
        ttk.Button(controls, text='Quet lai / cap lai Wi-Fi', command=self.retry).pack(side='left', padx=(0,8))
        ttk.Button(controls, text='Cho phep tra lai barcode', command=self.rearm).pack(side='left')
        manual = ttk.Frame(top); manual.grid(row=4, column=0, sticky='ew', pady=10)
        ttk.Label(manual, text='Barcode thu cong:').pack(side='left')
        self.manual = ttk.Entry(manual, width=24); self.manual.pack(side='left', padx=6)
        self.manual.bind('<Return>', lambda _: self.submit_manual())
        ttk.Button(manual, text='Tra', command=self.submit_manual).pack(side='left')
        ttk.Label(top, textvariable=self.vars['notice'], wraplength=1050).grid(row=5, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(top, text='Co IP chi xac nhan Wi-Fi. Firebase duoc truy van bang Internet cua laptop. Khong mo Serial Monitor cung luc.', wraplength=1050).grid(row=6, column=0, columnspan=2, sticky='w')
        ttk.Label(top, text='SAN PHAM CUA CUA HANG DANG CHON', font=('Segoe UI', 10, 'bold')).grid(row=7, column=0, columnspan=2, sticky='w', pady=8)
        self.details = scrolledtext.ScrolledText(top, height=15, wrap='word', font=('Consolas', 10), state='disabled')
        self.details.grid(row=8, column=0, columnspan=2, sticky='nsew')
        root.protocol('WM_DELETE_WINDOW', self.close)
        if start_workers:
            if speech:
                from speaker import Speaker
                self.speaker = Speaker(self.stop, self.get_identity, self.events)
                self.speaker.start()
            SerialWorker(port, self.events, self.outbound, self.stop).start()
            for _ in range(2): threading.Thread(target=self.network_worker, daemon=True).start()
            if not wifi_only:
                from camera import CameraWorker
                CameraWorker(model, camera, self.frames, self.events, self.stop, self.get_stamp).start()
        self.render(); root.after(40, self.tick)

    def get_identity(self):
        with self.shared_lock: return (self.shared_key, self.shared_stamp)

    def get_stamp(self):
        with self.shared_lock: return self.shared_stamp

    def network_worker(self):
        while not self.stop.is_set():
            try: job = self.network_jobs.get(timeout=.2)
            except queue.Empty: continue
            with self.shared_lock:
                active = self.shared_key if job.kind == 'resolve' else self.shared_stamp
            if job.stamp != active: continue
            try:
                result = self.backend.resolve(job.payload['uid']) if job.kind == 'resolve' else self.backend.product(job.payload['store_id'], job.payload['barcode'])
                self.events.put(('backend_result', job, result))
            except BackendError as exc:
                self.events.put(('backend_error', job, exc.code))
            except Exception:
                self.events.put(('backend_error', job, 'backend_unexpected_response'))

    def retry(self):
        self.controller.retry(); self.hide_secret(); self.blocked.clear(); self.render()

    def rearm(self):
        self.blocked.clear(); self.seen_at.clear()

    def submit_manual(self):
        self.controller.barcode(self.manual.get(), self.controller.camera_stamp, time.monotonic())
        self.render()

    def hide_secret(self):
        self.show_secret.set(False); self.secret_entry.configure(show='*')

    def toggle_secret(self):
        if not self.controller.wifi_credentials:
            self.hide_secret(); return
        self.secret_entry.configure(show='' if self.show_secret.get() else '*')
        if self.show_secret.get():
            identity = self.controller.key
            self.root.after(15000, lambda: self.hide_secret() if not self.closed and identity == self.controller.key else None)

    def render(self):
        c = self.controller
        if c.key != self.last_identity:
            self.last_identity = c.key; self.hide_secret()
        self.vars['status'].set(c.status)
        self.vars['rfid'].set(c.uid or 'Chua quet')
        self.vars['store'].set(f"{c.store['name']} | {c.store['id']}" if c.store else 'Chua co cua hang duoc xac thuc')
        self.vars['owner'].set(c.store['owner_uid'] if c.store else '-')
        self.vars['ssid'].set(c.wifi_credentials.get('ssid','Chua nhan'))
        self.vars['password'].set(c.wifi_credentials.get('password',''))
        self.reveal_button.state(['!disabled'] if c.wifi_credentials else ['disabled'])
        self.vars['wifi'].set(f"{c.phase}\nSSID: {c.wifi.get('ssid') or '-'} | IP: {c.wifi.get('ip') or '-'}\nAction: {c.wifi.get('action','-')} | reason: {c.wifi.get('reason',0)}\nReuse: {c.wifi.get('reuse_count',0)} | Switch: {c.wifi.get('switch_count',0)}")
        text = ''
        if c.product and c.store and c.ready:
            text = f"CUA HANG: {c.store['name']} ({c.store['id']})\nBARCODE: {c.product['barcode']}\nTRANG THAI: {c.product['status']}\n\n"
            text += json.dumps(c.product.get('fields',{}), ensure_ascii=False, indent=2)
        if text != self.last_product_text:
            self.details.configure(state='normal'); self.details.delete('1.0','end'); self.details.insert('end',text); self.details.configure(state='disabled')
            self.last_product_text = text

    def tick(self):
        if self.closed: return
        now = time.monotonic()
        for _ in range(100):
            try: event = self.events.get_nowait()
            except queue.Empty: break
            kind = event[0]
            if kind == 'opened': self.controller.opened(event[1], event[2], now)
            elif kind == 'closed': self.controller.disconnected(event[1])
            elif kind == 'snapshot':
                received_at = event[3] if len(event) > 3 else now
                if now - received_at <= 5:
                    self.controller.snapshot(event[1], event[2], received_at)
            elif kind == 'backend_result':
                job, result = event[1:]
                if job.kind == 'resolve': self.controller.resolved(job, result, now)
                else: self.controller.product_result(job, result)
            elif kind == 'backend_error': self.controller.failed(event[1], event[2])
            elif kind == 'notice': self.vars['notice'].set(event[1])
        self.controller.tick(now)
        stamp = self.controller.camera_stamp
        if stamp != self.last_camera_stamp:
            self.blocked.clear(); self.seen_at.clear(); self.last_camera_stamp = stamp
        with self.shared_lock:
            self.shared_key = self.controller.key
            self.shared_stamp = stamp
        for job in self.controller.jobs:
            try: self.network_jobs.put_nowait(job)
            except queue.Full: self.controller.failed(job, 'backend_queue_full')
        self.controller.jobs.clear()
        for command in self.controller.commands:
            try: self.outbound.put_nowait(command)
            except queue.Full:
                self.controller.disconnected(self.controller.connection_id)
                self.vars['notice'].set('USB queue day; hay dong va mo lai chuong trinh.')
                break
        self.controller.commands.clear()
        try:
            frame_stamp, image, readings, captured = self.frames.get_nowait()
            if image is not None:
                from PIL import Image, ImageTk
                picture = Image.fromarray(image); picture.thumbnail((520,350))
                self.photo = ImageTk.PhotoImage(picture)
                self.preview.configure(image=self.photo, text='')
            if stamp is not None and frame_stamp == stamp and now - captured < 3:
                for code in readings: self.seen_at[code] = now
                for code in list(self.blocked):
                    if code not in readings and now - self.seen_at.get(code, now) > 2: self.blocked.remove(code)
                self.seen_at = {k:v for k,v in self.seen_at.items() if now-v < 10}
                for code in sorted(readings - self.blocked):
                    if self.controller.barcode(code, stamp, now): self.blocked.add(code)
                    break
        except queue.Empty: pass
        if self.speaker:
            c = self.controller
            state = (c.key, c.ready, c.phase)
            if state != self.last_spoken_state:
                self.last_spoken_state = state
                if c.ready and c.store:
                    self.speaker.say((c.key, c.camera_stamp), 'Bạn đang ở cửa hàng ' + c.store['name'] + '. Đã kết nối Wi-Fi. Đưa mã vạch vào camera hoặc nhờ người hỗ trợ nhập mã.')
                elif c.phase == 'waiting_credentials': self.speaker.say((c.key, c.camera_stamp), 'Đã đọc thẻ. Đang tìm cửa hàng.')
                elif c.phase in ('wifi_failed', 'credentials_timeout', 'backend_error', 'disconnected'):
                    self.speaker.say((c.key, c.camera_stamp), 'Chưa sẵn sàng. Có lỗi kết nối hoặc xác thực. Cần kiểm tra chương trình.')
            if c.product and c.ready:
                product_key = (c.camera_stamp, c.request_number)
                if product_key != self.last_spoken_product:
                    self.last_spoken_product = product_key
                    if c.product['status'] == 'found':
                        f = c.product['fields']
                        self.speaker.say((c.key, c.camera_stamp), 'Cửa hàng ' + c.store['name'] + '. ' + '. '.join(str(k) + ': ' + str(v) for k,v in f.items()))
                    else: self.speaker.say((c.key, c.camera_stamp), 'Không tìm thấy sản phẩm trong cửa hàng này.' if c.product['status']=='not_found' else 'Có mã vạch trùng. Cần kiểm tra dữ liệu.')
        self.render(); self.root.after(40, self.tick)

    def close(self):
        self.closed = True; self.stop.set(); self.controller.clear_selection()
        self.vars['password'].set(''); self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Unified V6 RFID + Wi-Fi + barcode desktop client')
    parser.add_argument('--port', default='COM4')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--model', type=Path, default=ROOT/'models'/'barcode_best.pt')
    parser.add_argument('--backend', choices=('spark','functions'), default='spark')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--no-speech', action='store_true')
    parser.add_argument('--wifi-only', action='store_true')
    parser.add_argument('--test-backend', action='store_true')
    parser.add_argument('--test-rfid')
    args = parser.parse_args()
    if args.backend == 'spark':
        from spark_backend import SparkBackend, SparkConfig
        backend = SparkBackend(SparkConfig.load(args.config or Path(__file__).with_name('spark_config.json')))
    else:
        backend = Backend(DeviceConfig.load(args.config or Path(__file__).with_name('device_config.json')))
    if args.test_backend:
        result = backend.ping()
        print('BACKEND_OK project=' + result['project_id'] + ' device=' + result['device_id'])
        return
    if args.test_rfid:
        backend.ping()
        result = backend.resolve(args.test_rfid)
        print('STORE_OK id=' + result['store']['id'] + ' owner=' + result['store']['owner_uid'])
        print('WIFI_CONFIG_RECEIVED (password hidden; ESP32 connection NOT tested by this command)')
        return
    import tkinter as tk
    root = tk.Tk()
    DesktopApp(root, backend, args.port, args.model.expanduser().resolve(), args.camera, args.wifi_only, speech=not args.no_speech)
    root.mainloop()

if __name__ == '__main__':
    try: main()
    except BackendError as error: raise SystemExit(str(error)) from None
    except KeyboardInterrupt: pass

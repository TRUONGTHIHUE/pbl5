"""RFID_PYTHON_V3: YOLO + decoder on PC; Firebase authenticated by ESP32.
python rfid_barcode.py --port COM4
Requires firmware V3. No Firebase password is sent to Python.
"""
import argparse
import json
import os
import re
import urllib.request
import urllib.error
import queue
import threading
import time
from pathlib import Path


def firestore_value(value):
    """Preserve Firestore integer/barcode strings and show arbitrary product fields."""
    if not isinstance(value, dict):
        return value
    for key in ('stringValue', 'integerValue', 'doubleValue', 'booleanValue', 'timestampValue'):
        if key in value:
            return value[key]
    if 'nullValue' in value:
        return None
    if 'arrayValue' in value:
        return [firestore_value(v) for v in value['arrayValue'].get('values', [])]
    if 'mapValue' in value:
        return {k: firestore_value(v) for k, v in value['mapValue'].get('fields', {}).items()}
    return value


def parse_protocol(line):
    for prefix in ('@STORE:', '@WIFI:', '@PRODUCT:'):
        if line.startswith(prefix):
            try:
                data = json.loads(line[len(prefix):])
                return (prefix, data) if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


WIFI_PHASES = {
    'bootstrap': 'Chưa kết nối Wi-Fi, chờ quét thẻ',
    'waiting_pc_credentials': 'Chờ Python lấy Wi-Fi từ Firestore',
    'disconnected': 'Chưa có kết nối/IP',
    'ip_ready': 'Đã có IP; chưa xác minh Firebase trên kết nối này',
    'store_connecting': 'Đã lấy Wi-Fi cửa hàng; đang kết nối...',
    'store_ip_ready': 'Wi-Fi cửa hàng có IP; đang kiểm tra Firebase...',
    'store_firebase_ok': 'Wi-Fi cửa hàng: đã có IP và truy cập Firebase thành công',
    'credentials_missing': 'Thiếu/sai wifiSSID hoặc wifiPassword; dùng mạng hiện tại',
    'store_failed_fallback': 'Wi-Fi cửa hàng thất bại; đang quay về mạng ban đầu',
    'fallback_connecting': 'Đang khôi phục mạng ban đầu',
    'fallback_firebase_ok': 'Đang dùng mạng ban đầu; truy cập Firebase thành công',
    'fallback_failed': 'Không truy cập được Firebase sau khi quay về mạng ban đầu',
}


def firebase_json_post(url, data, token=None):
    """Access Firebase over HTTPS from the PC, never from ESP32 before Wi-Fi."""
    body = json.dumps(data).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Firebase HTTP {exc.code}; kiem tra tai khoan va Firestore Rules') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('May tinh khong truy cap duoc Firebase (mang/DNS/TLS)') from exc


def normalize_rfid(uid):
    normalized = re.sub(r'[\s:-]', '', str(uid)).upper()
    if len(normalized) not in (8, 14, 20) or not re.fullmatch(r'[0-9A-F]+', normalized):
        return None
    return normalized


def retrieve_wifi_from_firebase(rfid, config):
    auth_url = ('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key='
                + config['api_key'])
    auth = firebase_json_post(auth_url, {'email': config['email'],
                                         'password': config['password'],
                                         'returnSecureToken': True})
    owner_uid = auth['localId']
    query_url = (f"https://firestore.googleapis.com/v1/projects/{config['project_id']}"
                 '/databases/(default)/documents:runQuery')
    query = {'structuredQuery': {
        'from': [{'collectionId': 'stores'}],
        'where': {'fieldFilter': {'field': {'fieldPath': 'ownerUid'},
                                  'op': 'EQUAL', 'value': {'stringValue': owner_uid}}},
        'select': {'fields': [{'fieldPath': k} for k in
                              ('rfidId', 'storeName', 'wifiSSID', 'wifiPassword')]}
    }}
    rows = firebase_json_post(query_url, query, auth['idToken'])
    matches = []
    for row in rows:
        fields = row.get('document', {}).get('fields', {})
        get_string = lambda key: fields.get(key, {}).get('stringValue')
        if normalize_rfid(get_string('rfidId')) == normalize_rfid(rfid):
            matches.append((get_string('storeName'), get_string('wifiSSID'),
                            get_string('wifiPassword')))
    if len(matches) != 1:
        raise RuntimeError(f'UID RFID phai khop dung 1 cua hang; tim thay {len(matches)}')
    store_name, ssid, password = matches[0]
    if not isinstance(ssid, str) or not isinstance(password, str):
        raise RuntimeError('Thieu wifiSSID/wifiPassword dang string trong Firestore')
    if not (1 <= len(ssid.encode('utf-8')) <= 32) or len(password.encode('utf-8')) > 64:
        raise RuntimeError('SSID qua 32 byte hoac password qua 64 byte')
    return (store_name or 'Cua hang', ssid, password)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM4')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--model', default=str(Path(__file__).with_name('barcode_best.pt')))
    args = parser.parse_args()
    firebase_config = {
        'email': os.getenv('STORE_FIREBASE_EMAIL', ''),
        'password': os.getenv('STORE_FIREBASE_PASSWORD', ''),
        'api_key': os.getenv('STORE_FIREBASE_API_KEY', ''),
        'project_id': os.getenv('STORE_FIREBASE_PROJECT_ID', ''),
    }
    if not all(firebase_config.values()):
        raise SystemExit('Thieu bien moi truong STORE_FIREBASE_EMAIL, '
                         'STORE_FIREBASE_PASSWORD, STORE_FIREBASE_API_KEY, '
                         'STORE_FIREBASE_PROJECT_ID. Xem README.')
    if not Path(args.model).is_file():
        raise SystemExit(f'Không tìm thấy trọng số: {args.model}')
    import cv2
    import serial
    import tkinter as tk
    from tkinter import scrolledtext
    from ultralytics import YOLO
    from pyzbar.pyzbar import decode

    root = tk.Tk()
    root.title('RFID + Barcode + Firebase — V4 Wi-Fi PC')
    root.geometry('770x650')
    shop_text = tk.StringVar(value='Hãy quét thẻ RFID sau khi camera mở.')
    wifi_text = tk.StringVar(value='Đang chờ trạng thái Wi-Fi ESP32...')
    status_text = tk.StringVar(value='Đang tải mô hình...')
    for variable in (shop_text, wifi_text, status_text):
        tk.Label(root, textvariable=variable, justify='left', anchor='w', wraplength=740,
                 font=('Segoe UI', 11)).pack(fill='x', padx=12, pady=7)
    details = scrolledtext.ScrolledText(root, font=('Consolas', 11), wrap='word', height=20)
    details.pack(fill='both', expand=True, padx=12, pady=8)
    root.update()
    model = YOLO(args.model)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        root.destroy()
        raise SystemExit('Không mở được camera. Thử --camera 1')
    stop = threading.Event()
    incoming, outgoing, sounds = queue.Queue(), queue.Queue(), queue.Queue()
    wifi_jobs = queue.Queue()
    gen, store, pending = None, None, None
    request_id = 0
    blocked = set()
    seen_at = {}
    last_serial = time.monotonic()
    last_wifi = None
    last_barcode = None

    def show(text):
        details.configure(state='normal')
        details.delete('1.0', 'end')
        details.insert('end', text)
        details.configure(state='disabled')

    def sound_worker():
        try:
            import winsound
        except ImportError:
            winsound = None
        while not stop.is_set():
            try:
                kind = sounds.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                if winsound:
                    notes = {'store': [(1000, 100)], 'found': [(1200, 120), (1600, 160)],
                             'missing': [(450, 200)], 'error': [(350, 100), (350, 100)]}[kind]
                    for hz, ms in notes:
                        winsound.Beep(hz, ms)
                else:
                    print('\a', end='', flush=True)
            except (RuntimeError, OSError):
                pass

    def serial_worker():
        try:
            with serial.Serial(args.port, 115200, timeout=.05, write_timeout=2) as connection:
                incoming.put(('notice', f'Đã mở {args.port}. Tháo thẻ và quét lại.'))
                buffer = b''
                last_poll = 0
                while not stop.is_set():
                    now = time.monotonic()
                    if now - last_poll >= 3:
                        connection.write(b'@CMD:{"command":"status"}\n')
                        last_poll = now
                    try:
                        cmd = outgoing.get_nowait()
                    except queue.Empty:
                        cmd = None
                    if cmd:
                        connection.write(('@CMD:' + json.dumps(cmd, ensure_ascii=True) + '\n').encode())
                    buffer += connection.read(min(connection.in_waiting or 1, 4096))
                    while b'\n' in buffer:
                        raw, buffer = buffer.split(b'\n', 1)
                        line = raw.decode('utf-8', errors='replace').strip()
                        if 'RFID_PYTHON_V4_PC_WIFI' in line or line.startswith('ets Jul'):
                            incoming.put(('reset', None))
                        elif 'RFID_PYTHON_V3' in line or 'RFID_PYTHON_V2' in line:
                            incoming.put(('fatal', 'ESP32 dang chay firmware cu. Can nap main V4_PC_WIFI.'))
                        else:
                            event = parse_protocol(line)
                            if event:
                                incoming.put(event)
                            elif 'FIREBASE:' in line or 'STORE_RFID:' in line:
                                print(line)
                    if len(buffer) > 32768:
                        buffer = b''
        except (serial.SerialException, OSError) as exc:
            incoming.put(('fatal', f'Lỗi COM: {exc}. Đóng idf_monitor và mở lại chương trình.'))

    def wifi_lookup_worker():
        while not stop.is_set():
            try:
                generation, rfid = wifi_jobs.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                shop, ssid, password = retrieve_wifi_from_firebase(rfid, firebase_config)
                outgoing.put({'command': 'wifi', 'generation': generation,
                              'ssid': ssid, 'password': password})
                incoming.put(('wifi_fetch_ok', f'Da tim thay {shop}; gui SSID {ssid} cho ESP32'))
            except (RuntimeError, KeyError, ValueError, TypeError) as exc:
                incoming.put(('wifi_fetch_error', f'Khong lay duoc Wi-Fi: {exc}'))

    def retry():
        nonlocal last_barcode
        if pending is None:
            blocked.clear()
            last_barcode = None
            status_text.set('Đưa mã vạch vào camera để tra lại.')

    tk.Button(root, text='Tra lại sản phẩm (hoặc nhấn R tại camera)', command=retry).pack(pady=6)
    root.protocol('WM_DELETE_WINDOW', stop.set)
    threads = [threading.Thread(target=serial_worker, daemon=True),
               threading.Thread(target=sound_worker, daemon=True),
               threading.Thread(target=wifi_lookup_worker, daemon=True)]
    for thread in threads:
        thread.start()
    status_text.set('Quét RFID để chọn cửa hàng.')
    print('V4: Python cấp Wi-Fi theo thẻ, ESP32 tra Firebase. Q để thoát camera; R để tra lại. Âm thanh phát từ máy tính.')
    try:
        while not stop.is_set():
            root.update()
            now = time.monotonic()
            while True:
                try:
                    kind, data = incoming.get_nowait()
                except queue.Empty:
                    break
                if kind in ('reset', 'fatal'):
                    gen, store, pending = None, None, None
                    blocked.clear(); seen_at.clear(); last_wifi = None; last_barcode = None
                    shop_text.set('Chưa chọn cửa hàng')
                    wifi_text.set('Đang chờ ESP32...')
                    show('')
                    status_text.set(data or 'ESP32 vừa khởi động. Hãy quét thẻ.')
                    if kind == 'fatal':
                        sounds.put('error')
                    continue
                if kind == 'notice':
                    print(data)
                    continue
                if kind in ('wifi_fetch_ok', 'wifi_fetch_error'):
                    status_text.set(data)
                    print(data)
                    continue
                last_serial = now
                if kind == '@STORE:':
                    event = data.get('event')
                    newgen = data.get('generation')
                    if event == 'scanning':
                        gen, store, pending = newgen, None, None
                        blocked.clear(); seen_at.clear(); last_barcode = None
                        show(''); shop_text.set('Đang tìm cửa hàng...')
                        status_text.set('Python đang tìm Wi-Fi cửa hàng trên Firebase...')
                        if data.get('rfid_uid'):
                            wifi_jobs.put((newgen, data['rfid_uid']))
                    elif event == 'identified' and newgen == gen:
                        shop_text.set(f"Đã tìm thấy: {data.get('store_name')} | ID: {data.get('store_id')}")
                        loaded = data.get('wifi_credentials_loaded', False)
                        status_text.set('Đã lấy cấu hình Wi-Fi: ' + data.get('store_ssid', '') if loaded
                                        else 'Chưa lấy được cấu hình Wi-Fi hợp lệ của cửa hàng.')
                    elif event == 'ready' and (gen is None or newgen == gen) and data.get('store_id'):
                        changed = not store or (gen, store.get('store_id')) != (newgen, data['store_id'])
                        gen, store = newgen, data
                        shop_text.set(f"Cửa hàng: {data.get('store_name')}\nID: {data['store_id']}")
                        if changed:
                            pending = None; blocked.clear(); seen_at.clear(); show('')
                            status_text.set('Sẵn sàng: đưa barcode vào camera. Wi-Fi cửa hàng: ' +
                                            ('đã đọc cấu hình' if data.get('wifi_credentials_loaded') else 'thiếu/sai định dạng cấu hình'))
                            sounds.put('store')
                    elif event == 'error' and newgen == gen:
                        store, pending = None, None
                        show(''); status_text.set('Không xác định được cửa hàng/kết nối. Kiểm tra terminal và quét lại.')
                        sounds.put('error')
                elif kind == '@WIFI:' and (gen is None or data.get('generation') == gen):
                    phase_name = data.get('phase', '')
                    text = WIFI_PHASES.get(phase_name, phase_name)
                    wifi_text.set(f"Wi-Fi ESP32: {text}\nSSID thực tế: {data.get('ssid') or '—'} | IP: {data.get('ip') or '—'}")
                    if data != last_wifi:
                        print('WIFI:', text, '| SSID:', data.get('ssid'), '| IP:', data.get('ip'))
                        last_wifi = data
                elif kind == '@PRODUCT:' and store and pending and data.get('generation') == gen:
                    if data.get('request_id') != pending['request_id'] or data.get('barcode') != pending['barcode']:
                        continue
                    barcode = pending['barcode']; pending = None
                    result = data.get('status')
                    heading = f"CỬA HÀNG: {store.get('store_name')}\nBARCODE: {barcode}\n\n"
                    if result == 'found':
                        fields = {key: firestore_value(value) for key, value in data.get('fields', {}).items()}
                        show(heading + 'ĐÃ CÓ TRONG CỬA HÀNG\n\n' + '\n'.join(f'{k}: {v}' for k, v in fields.items()))
                        status_text.set('Tìm thấy sản phẩm. Kết quả được giữ lại bên dưới.')
                        sounds.put('found')
                        print('TIM THAY:', json.dumps(fields, ensure_ascii=False))
                    elif result == 'not_found':
                        show(heading + 'KHÔNG TÌM THẤY trong cửa hàng này.\nKiểm tra barcode dạng string và đúng subcollection products.')
                        status_text.set('Barcode chưa có trong cửa hàng đã chọn.')
                        sounds.put('missing')
                    else:
                        message = 'Có nhiều sản phẩm cùng barcode. Cần kiểm tra dữ liệu.' if result == 'duplicate' else 'Tra cứu thất bại/bận. Kiểm tra mạng và Firestore Rules; nhấn Tra lại.'
                        show(heading + message)
                        status_text.set(message)
                        sounds.put('error')
            if store and now - last_serial > 12:
                store, pending, gen = None, None, None
                blocked.clear(); show('')
                status_text.set('Mất phản hồi ESP32. Kiểm tra COM/nguồn, sau đó quét lại.')
            if pending and now - pending['started'] > 100:
                pending = None
                status_text.set('Hết thời gian chờ Firebase. Kiểm tra terminal và nhấn Tra lại.')
                sounds.put('error')
            ok, source = cap.read()
            if not ok:
                status_text.set('Không đọc được camera. Đóng và chạy lại.')
                root.update()
                break
            frame = source.copy()
            readings = set()
            if store:
                result = model.predict(source, imgsz=640, conf=.4, verbose=False)[0]
                h, w = source.shape[:2]
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())
                    left, top, right, bottom = max(0, x1-20), max(0, y1-20), min(w, x2+20), min(h, y2+20)
                    crop = source[top:bottom, left:right]
                    if not crop.size:
                        continue
                    codes = decode(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 255), 2)
                    for item in codes:
                        try:
                            code = item.data.decode('utf-8', errors='strict')
                        except UnicodeDecodeError:
                            continue
                        if 0 < len(code.encode('utf-8')) <= 128:
                            readings.add(code)
                            cv2.putText(frame, code, (left, max(20, top-8)), cv2.FONT_HERSHEY_SIMPLEX, .6, (0,255,255), 2)
                # Rearm only after the code has been absent for two seconds.
                now = time.monotonic()
                for code in readings:
                    seen_at[code] = now
                for code in list(blocked):
                    if code not in readings and now - seen_at.get(code, now) > 2:
                        blocked.remove(code)
                seen_at = {k: v for k, v in seen_at.items() if now - v < 10}
                if pending is None:
                    candidates = sorted(readings - blocked)
                    if candidates:
                        code = candidates[0]
                        request_id = (request_id + 1) % 2**32
                        pending = {'request_id': request_id, 'barcode': code, 'started': now}
                        blocked.add(code); last_barcode = code
                        outgoing.put({'command': 'product', 'generation': gen, 'request_id': request_id, 'barcode': code})
                        status_text.set(f'Đã đọc {code}. Đang tra Firebase của {store.get("store_name")}...')
            cv2.putText(frame, 'See product/Wi-Fi in result window. Q: quit | R: retry', (10,25), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
            cv2.imshow('Barcode camera V3', frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord('r'):
                retry()
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2.5)
        cap.release()
        cv2.destroyAllWindows()
        root.destroy()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

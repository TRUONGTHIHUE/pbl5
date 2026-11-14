"""Camera/YOLO/decoder run away from Tk and USB heartbeat threads."""
from __future__ import annotations
from pathlib import Path
import queue
import threading
import time
from protocol import valid_text


def decode_barcodes(source, model, decode, cv2) -> tuple[object, set[str]]:
    frame = source.copy()
    readings: set[str] = set()
    result = model.predict(source, imgsz=640, conf=.4, verbose=False)[0]
    h, w = source.shape[:2]
    crops = []
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())
        left, top, right, bottom = max(0, x1-20), max(0, y1-20), min(w, x2+20), min(h, y2+20)
        if right <= left or bottom <= top: continue
        crops.append(source[top:bottom, left:right])
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 255), 2)
    # Preserve YOLO ROI decoding; full-frame fallback avoids missing a readable code
    # solely because the detector missed its box. This does not certify accuracy.
    if not crops: crops.append(source)
    for crop in crops:
        for item in decode(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)):
            try:
                value = item.data.decode('utf-8', errors='strict')
            except (UnicodeError, AttributeError):
                continue
            if valid_text(value, 128): readings.add(value)  # Never int(value).
    return frame, readings


class CameraWorker(threading.Thread):
    def __init__(self, model_path: Path, camera_id: int, frames: queue.Queue, notices: queue.Queue,
                 stop: threading.Event, get_stamp):
        super().__init__(daemon=True)
        self.model_path, self.camera_id = model_path, camera_id
        self.frames, self.notices, self.stop, self.get_stamp = frames, notices, stop, get_stamp

    def run(self) -> None:
        cap = None
        try:
            if not self.model_path.is_file():
                self.notices.put(('notice', 'Khong thay model. Kiem tra --model; Wi-Fi/manual barcode van dung duoc.'))
                return
            import cv2
            from ultralytics import YOLO
            from pyzbar.pyzbar import decode
            model = YOLO(str(self.model_path))
            cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                self.notices.put(('notice', 'Khong mo duoc camera. Thu --camera 1; Wi-Fi/manual barcode van dung duoc.'))
                return
            self.notices.put(('notice', 'Camera va model da mo. Chi tra barcode khi dung cua hang va Wi-Fi co IP.'))
            failures = 0
            while not self.stop.is_set():
                stamp = self.get_stamp()
                ok, source = cap.read()
                if not ok:
                    failures += 1
                    if failures >= 10: raise OSError('camera_read_failed')
                    self.stop.wait(.1); continue
                failures = 0
                frame, readings = decode_barcodes(source, model, decode, cv2) if stamp is not None else (source, set())
                packet = (stamp, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), readings, time.monotonic())
                try: self.frames.put_nowait(packet)
                except queue.Full:
                    try: self.frames.get_nowait()
                    except queue.Empty: pass
                    try: self.frames.put_nowait(packet)
                    except queue.Full: pass
        except ImportError:
            self.notices.put(('notice', 'Thieu thu vien camera/YOLO/pyzbar hoac ZBar DLL. Xem huong dan Windows.'))
        except Exception:
            self.notices.put(('notice', 'Camera/model/decoder gap loi. Wi-Fi tiep tuc; kiem tra dependency/model va khoi dong lai.'))
        finally:
            if cap is not None: cap.release()

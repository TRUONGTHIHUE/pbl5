# Chạy V6 trên Windows

Các lệnh dưới đây là hướng dẫn để bạn thực hiện trên máy của mình.
Trong lần bàn giao, chưa có lệnh flash hoặc deploy nào được chạy trên hệ thống của bạn.

## 1. Thư mục và công cụ

Giải nén toàn bộ ZIP vào một đường dẫn ngắn, ví dụ `D:\PBL5_UNIFIED_V6`.
Đây là project riêng, **không chép lẫn V6 vào main/Python V4 hoặc V5**.

Cần Python 3.11 64-bit cho ứng dụng PC, ESP-IDF 5.5.5 cho firmware,
Node.js 22 + Firebase CLI cho triển khai backend.
Camera/model chưa được kiểm thử trên máy của bạn.

Phân biệt hai cửa sổ:
- **PowerShell thường:** chạy Python PC, npm/Firebase.
- **ESP-IDF Terminal 5.5.5:** chạy idf.py. Không thay Python môi trường ESP-IDF
  bằng virtualenv của ứng dụng camera.

Không cần đặt ExecutionPolicy toàn máy hoặc chạy mọi thứ bằng Administrator.
Các lệnh gọi trực tiếp python.exe trong venv không cần Activate.ps1.

## 2. Tạo môi trường Python

PowerShell:

```powershell
cd D:\PBL5_UNIFIED_V6
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Chỉ thử Wi-Fi/Serial trước:

```powershell
.\.venv\Scripts\python.exe -m pip install -r pc\requirements-wifi.txt
```

Để chạy camera/YOLO/barcode, cài thêm bộ đầy đủ:

```powershell
.\.venv\Scripts\python.exe -m pip install -r pc\requirements.txt
```

Cài đầy đủ có thể tải Torch/Ultralytics và các dependency lớn.
Không ghi nhận đây là cài đặt đã được kiểm tra trên Windows; nếu phát sinh lỗi,
giữ nguyên terminal error và phiên bản Python để chẩn đoán.

Kiểm tra imports:

```powershell
.\.venv\Scripts\python.exe -c "import tkinter,serial; print('GUI_SERIAL_IMPORT_OK')"
.\.venv\Scripts\python.exe -c "import cv2; from ultralytics import YOLO; from pyzbar.pyzbar import decode; print('CAMERA_IMPORT_OK')"
```

Nếu pyzbar báo thiếu libzbar/DLL, xử lý đúng dependency Windows theo tài liệu pyzbar.
Không tải DLL lạ từ website không rõ nguồn. Import thành công chưa chứng minh camera/model chạy.

Model đã có tại `models\barcode_best.pt`. File này giữ nguyên từ repo, không tự train lại.
Có thể kiểm tra hash:

```powershell
Get-FileHash .\models\barcode_best.pt -Algorithm SHA256
Get-Content .\models\SHA256SUMS
```

## 3. Backend, thiết bị và Firestore

Làm theo `FIREBASE_SETUP.md`. Phải có:
- function `deviceApiV6` được chính bạn deploy vào project đúng;
- `pc\device_config.json` chứa endpoint, device ID, token bí mật và project ID;
- `devices/{deviceId}` có hash token, enabled=true;
- cửa hàng có dữ liệu đúng, RFID canonical, Wi-Fi thật;
- `stores/{storeId}/authorizedDevices/{deviceId}` enabled=true.

Không nhập email/password chủ cửa hàng vào PowerShell nữa.
Thông tin đăng nhập `firebase login` là quyền quản trị triển khai một lần,
không phải thông tin Python sử dụng khi chạy máy quét.

Kiểm tra riêng backend, chưa cần ESP32:

```powershell
.\.venv\Scripts\python.exe pc\app.py --test-backend
.\.venv\Scripts\python.exe pc\app.py --test-rfid "CD 4B 1E 03"
```

Log thành công mong đợi, không phải log chạy thật đã ghi nhận:

```text
BACKEND_OK project=quanlycuahang-afb59 device=may-quet-01
STORE_OK id=<document ID thực tế> owner=<ownerUid thực tế>
WIFI_CONFIG_RECEIVED (password hidden; ESP32 connection NOT tested by this command)
```

Đổi tham số RFID theo thẻ thực tế. Không gán tự động UID ví dụ cho document đã biết.

## 4. Đấu RC522

Tắt nguồn trước khi chỉnh dây.

| RC522 | ESP32 mặc định |
|---|---|
| VCC/3.3V | 3.3V |
| GND | GND |
| SDA/SS | GPIO21 |
| SCK | GPIO18 |
| MOSI | GPIO23 |
| MISO | GPIO19 |
| RST | GPIO22 |

Chân có thể chỉnh trong menuconfig của V6.
Dùng nguồn 3.3V cho RC522 theo phần cứng hiện tại.
Mạng kiểm thử phải có 2.4 GHz tương thích; implementation nhắm mạng open hoặc WPA2-PSK,
không cung cấp luồng enterprise/captive portal.

## 5. Build và nạp firmware

Mở **ESP-IDF Terminal 5.5.5**, tại root mới:

```text
cd /d D:\PBL5_UNIFIED_V6
idf.py --version
idf.py set-target esp32
idf.py build
idf.py -p COM4 flash monitor
```

Dòng `cd /d` dùng trong ESP-IDF CMD. Nếu ESP-IDF mở PowerShell, dùng:
```powershell
cd D:\PBL5_UNIFIED_V6
```

`set-target` dùng lần đầu trong project mới, không cần chạy mỗi lần thêm cửa hàng.
Nếu idf.py --version không phải 5.5.5, mở đúng môi trường trước khi build.

Component manager cần mạng để lấy `abobija/rc522:4.0.1` lần đầu.
File sdkconfig.defaults chọn flash4MB theo chip đã báo trong log trước;
nếu board khác có dung lượng khác, chỉnh đúng phần cứng bằng menuconfig/partition.
Không cố flash cấu hình vượt dung lượng board.

Project chỉ có factory partition, không triển khai OTA.
Không chạy erase-flash tùy tiện: thao tác đó xóa NVS/dữ liệu cũ.
V6 không dùng credential cố định cũ; chọn RAM không tự xóa các entry NVS tồn tại trước đó.

Log mong đợi:

```text
I (...) PBL5: VERSION: PBL5_UNIFIED_V6 protocol=2; no hardcoded Wi-Fi/Firebase credentials
I (...) PBL5: RC522_READY ...
@STATE:{"v":2,"firmware":"PBL5_UNIFIED_V6",...}
```

**Thoát Monitor bằng Ctrl + ]** trước khi mở Python.
Không giữ Monitor và Python cùng sử dụng COM4.

## 6. Chạy Wi-Fi trước

Laptop kết nối Internet bằng Wi-Fi trọ. ESP32 vẫn nối USB.

PowerShell thường:

```powershell
cd D:\PBL5_UNIFIED_V6
.\.venv\Scripts\python.exe pc\app.py --port COM4 --wifi-only
```

`--wifi-only` không tải camera/YOLO; vẫn có ô nhập barcode thủ công để thử backend sản phẩm.

Quét thẻ, nhấc thẻ ra. GUI lần lượt:
- chờ/quét RFID;
- xác thực thiết bị và tìm cửa hàng;
- nhận cấu hình/gửi USB;
- ESP32 kết nối hoặc giữ mạng chung;
- `SAN SANG`, đúng store ID, có IP.

Mật khẩu che mặc định. Chỉ bật hiện tạm khi cần; không chụp màn hình gửi mật khẩu.
Nếu lỗi, không đoán rằng đã lấy được IP hoặc Firebase đã deploy chỉ từ thông báo cấu hình.

Thẻ khác nhưng Wi-Fi giống: store ID đổi, IP có thể giữ nguyên, action=`reused`,
reuse_count tăng, switch_count không tăng vì quét thẻ đó.
SSID chỉ là cấu hình mạng, không phải khóa phân biệt cửa hàng.

## 7. Mở camera và barcode

Đóng ứng dụng Wi-Fi-only trước:

```powershell
.\.venv\Scripts\python.exe pc\app.py --port COM4
```

Camera khác:

```powershell
.\.venv\Scripts\python.exe pc\app.py --port COM4 --camera 1
```

Model khác:

```powershell
.\.venv\Scripts\python.exe pc\app.py --port COM4 --model "D:\models\barcode_best.pt"
```

Ứng dụng đầy đủ đã có bước chọn RFID/cấp Wi-Fi; không chạy thêm chương trình Wi-Fi riêng.
Barcode giữ chuỗi, ví dụ `0012345678905`.
Chỉ khi đúng cửa hàng + firmware ready + Wi-Fi có IP thì mới tra sản phẩm.

Lỗi camera/model không được xem là lỗi Wi-Fi: GUI vẫn cho kiểm tra mạng và nhập barcode.
Model tồn tại trên đĩa chưa chứng minh chất lượng nhận diện.

## 8. Mở lại Python, mất Serial, ESP reset

Đóng Python rồi mở lại khi ESP đang chạy: client ID mới khiến firmware chọn generation mới,
dùng UID cuối trong RAM để hỏi backend lại. Không tự tin phiên cũ mà bỏ qua xác thực.
Nếu ESP reset mất UID trong RAM, quét thẻ lại.

Rút/cắm USB: SerialWorker thử mở lại, tạo client mới, chặn kết quả cũ.
Nếu Windows đổi COM, đóng chương trình và chạy đúng `--port`.
Một số driver USB có thể reset ESP khi mở cổng dù đã đặt DTR/RTS trước;
code xử lý boot ID mới, nhưng phải kiểm thử thực tế board/driver.

Nếu thấy `waiting for download`: nhả BOOT, nhấn EN/RESET.
Nếu `Access is denied`: đóng mọi chương trình đang giữ COM4 trước.

## 9. Lỗi cần phân biệt

| Hiện tượng | Kiểm tra |
|---|---|
| Thiếu device_config.json | Đăng ký thiết bị một lần, đúng thư mục pc |
| protocol/service/project mismatch | Firmware V6, function deviceApiV6, project đúng |
| 401 device_not_authenticated | Hash token/device ID/enabled |
| store_not_authorized | Grant authorizedDevices của đúng document |
| store_not_found | RFID canonical và thuộc đúng project |
| duplicate_rfid | Cùng RFID bị gán nhiều store; sửa dữ liệu, không chọn đại store đầu |
| duplicate barcode | Hai product trong cùng store có cùng chuỗi barcode |
| connect_timeout | SSID/pass, mạng2.4GHz, tín hiệu, router/DHCP; không kết luận chỉ do sai pass |
| Mất Wi-Fi | GUI ngừng barcode, ESP thử nối lại; không dùng kết quả cũ |
| Không có phản hồi V6 | Sai firmware, USB/baud/BOOT hoặc COM bị chiếm |
| libzbar/DLL/model/camera | Dependency, đường dẫn và quyền camera riêng |
| Có IP nhưng mạng không có Internet | V6 chỉ chứng minh IP ESP; Firebase vẫn do laptop truy cập |

## 10. Tự chạy test

Trong venv có dependency test, Node22; GCC là tùy chọn trên Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r pc\requirements-dev.txt
.\.venv\Scripts\python.exe scripts\run_checks.py
.\.venv\Scripts\python.exe tests\gui_smoke.py
```

Nếu thiếu GCC hoặc ZBar thì một số bước có thể skip; đọc output, không cộng chúng thành PASS.
`gui_smoke.py` dùng giả lập, không cần board và không phải kiểm thử camera.

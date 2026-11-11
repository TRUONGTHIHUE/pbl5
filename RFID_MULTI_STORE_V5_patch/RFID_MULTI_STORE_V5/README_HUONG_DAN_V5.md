# ESP32 + RC522 + Firebase: một bộ quét dùng cho nhiều chủ cửa hàng (V5)

## 0. Điều thay đổi so với V4

**V4 không đúng cho hệ thống nhiều chủ:** Python và ESP32 đăng nhập bằng email/mật khẩu của **một** chủ rồi lọc `ownerUid`. V5 bỏ hoàn toàn bước đăng nhập bằng tài khoản chủ cửa hàng ở ESP32/Python.

Luồng mới:

```text
RC522 quét UID thẻ
  -> ESP32 V5 gửi @STORE:scanning qua USB/COM4
  -> Python V5 (PC có Internet) gửi UID + danh tính thiết bị tới HTTPS Cloud Function
  -> Cloud Function xác thực token của máy quét; tìm stores.rfidId
  -> Cloud Function kiểm tra stores/{storeId}/authorizedDevices/{deviceId}
  -> Backend trả store_id, store_name và Wi-Fi tương ứng (chỉ cho máy đã được cấp quyền)
  -> Python gửi Wi-Fi qua USB; ESP32 kết nối Wi-Fi của cửa hàng (nhận IP)
  -> Quét barcode: Python hỏi Cloud Function lấy products của đúng store_id
  -> GUI hiển thị sản phẩm
```

**Máy tính phải có Internet và nối USB liên tục.** Không thể truy vấn Firebase bằng ESP32 khi chưa có đường truyền Internet. Wi-Fi cửa hàng cấp cho ESP32 là một bước riêng: Python đã có Internet độc lập; backend/product lookup chạy trên Python. ESP32 V5 xác nhận **kết nối Wi-Fi có IP**, không chứng minh được Wi-Fi có Internet. Nếu cần ESP32 tự gửi dữ liệu lên Firebase, phải xây chức năng riêng.

**Không lưu** email/mật khẩu Google/Firebase chủ cửa hàng, Wi-Fi cố định, hay service-account JSON trong ESP32/Python. Có **một token thiết bị riêng**, sinh một lần, nằm trong `device_config.json` trên PC. Token đó không phải mật khẩu của chủ cửa hàng; token có thể bị thu hồi bằng cách đặt `devices/{id}.enabled=false`. Không dùng UID RFID một mình làm quyền đọc mật khẩu (UID có thể sao chép).

Bản này là **bản vá mã nguồn**; chưa được thử thực tế trên board/Firestore của bạn. Hãy làm trên bản sao dự án trước khi nạp vào thiết bị đang vận hành.

## 1. Các thư mục trong ZIP

```text
RFID_MULTI_STORE_V5/
  main/
    main.c                 <- thay main của ESP-IDF
    store_codec.c/.h      <- dùng cùng cấu trúc gốc
    CMakeLists.txt
    Kconfig.projbuild
    idf_component.yml
  functions/
    index.js              <- Firebase Functions backend
    api_helpers.js
    package.json
    tests/
  pc/
    rfid_barcode.py       <- Python camera/YOLO
    provision_device.py   <- tạo token thiết bị một lần
    requirements.txt
    device_config.example.json
  FIRESTORE_RULES_FRAGMENT.txt
```

## 2. Tạo backend Firebase Functions (khác Hosting)

1. **Sao lưu website Firebase** của bạn và thư mục đang chứa `firebase.json`.
2. Mở CMD/PowerShell tại **thư mục website Firebase**, không phải thư mục ESP-IDF. Chạy `firebase login`, sau đó `firebase use` kiểm tra đúng project.
3. Nếu chưa có `functions/`, chạy:

```powershell
firebase init functions
```

Chọn đúng dự án, JavaScript, cài dependency nếu được hỏi. Cloud Functions thường yêu cầu project Firebase bật **Blaze/billing**; xem giá trước khi triển khai.

4. Chép `functions/index.js` và `functions/api_helpers.js` trong ZIP vào thư mục `functions/` của website. Nếu website **đã có functions/index.js**, **KHÔNG ghi đè**: hãy gộp thêm import/export của `deviceApi` và giữ nguyên functions cũ. Nếu functions mới hoàn toàn, có thể dùng `package.json` trong ZIP.
5. Trong thư mục `functions/`, cài thư viện:

```powershell
npm install firebase-admin firebase-functions
```

6. Từ thư mục website có `firebase.json`, chạy:

```powershell
firebase deploy --only functions:deviceApi
```

**KHÔNG dùng** `firebase deploy --only hosting` để cập nhật function này. Sau deploy, CLI hiển thị **Function URL**, dạng:

```text
https://asia-southeast1-MA_PROJECT.cloudfunctions.net/deviceApi
```

**Hãy sao chép đúng URL thực tế**, không dùng `MA_PROJECT` trong ví dụ. Firebase CLI phải biết cấu hình `functions` trong `firebase.json`; nếu trước đó chỉ có Hosting, `firebase init functions` sẽ bổ sung mà không cần xóa cấu hình Hosting.

> Lưu ý: Admin SDK trong Cloud Function truy cập Firestore với quyền máy chủ, bỏ qua Security Rules. Vì thế mã `deviceApi` đã **tự kiểm tra** token của thiết bị và quyền `authorizedDevices` trước khi đọc/trả mật khẩu hoặc sản phẩm. Không mở Firestore Rules công khai.

## 3. Sinh thông tin thiết bị (chỉ một lần)

Chép `pc/rfid_barcode.py`, `pc/provision_device.py`, `pc/requirements.txt` vào **thư mục gốc ESP-IDF** nằm cạnh `barcode_best.pt`. Mở PowerShell tại đó.

Chạy lệnh (thay URL function thật):

```powershell
python provision_device.py --device-id may-quet-01 --endpoint "https://asia-southeast1-MA_PROJECT.cloudfunctions.net/deviceApi"
```

Lệnh tạo file `device_config.json` chứa **token bí mật được sinh ngẫu nhiên** và in ra mã `tokenSha256` (64 ký tự hex) để bạn đưa vào Firestore. **Không tự nhập token gốc, không gửi `device_config.json` cho người khác và không đẩy file lên Hosting/GitHub.** Chạy lại lệnh khi file đã tồn tại sẽ bị từ chối để tránh làm mất khóa cũ.

## 4. Tạo quyền cho máy quét trong Firestore Console

Mở **Firebase Console -> Build -> Firestore Database -> Data**.

### 4a) Đăng ký thiết bị (1 lần cho máy quét)

Tạo document `devices/may-quet-01` với 2 field:

| Field | Firestore Type | Value |
|---|---|---|
| `enabled` | boolean | `true` |
| `tokenSha256` | string | chuỗi 64 ký tự từ màn hình `provision_device.py` |

Document `devices` không được client thường đọc/ghi; quản trị viên tạo trong Firebase Console. **Chỉ hash**, không dán token gốc vào Firestore.

### 4b) Mỗi cửa hàng giữ dữ liệu sẵn có

Ví dụ document `stores/<storeDocumentId>`:

```text
ownerUid:      "UID_CHU_A"
storeName:     "Cua hang A"
rfidId:        "C79A0C03"
wifiSSID:      "WiFi_CuaHang_A"
wifiPassword:  "MatKhauViDu123"
```

`rfidId` phải là **chuỗi HEX chữ HOA, không có dấu ':' hoặc '-'**, ví dụ UID của bạn từ log là `C79A0C03`. Với nhiều cửa hàng, mỗi UID phải duy nhất trên toàn bộ collection `stores` (không chỉ trong cùng một chủ). Các cửa hàng vẫn giữ nguyên `ownerUid` của chủ, nhưng backend không lọc theo ownerUid của tài khoản đang đăng nhập.

### 4c) Cấp quyền của từng cửa hàng cho máy quét

Dưới `stores/<storeDocumentId>`, tạo subcollection `authorizedDevices`; trong đó tạo document **ID bằng `may-quet-01`**, có:

```text
enabled: true   (boolean)
```

Lặp lại cho mỗi cửa hàng được phép sử dụng máy quét chung. Nếu thêm cửa hàng/chủ mới, chỉ cần tạo cửa hàng và cấp quyền `authorizedDevices`, **không nhập mật khẩu chủ mới vào PC** và không cần nạp lại ESP32.

Các `authorizedDevices` là danh sách cho phép; biết UID thẻ nhưng không có token thiết bị **và** không được chủ cấp quyền thì không lấy được Wi-Fi. Sau này có thể bổ sung nút "Cho phép thiết bị" trên website chủ cửa hàng; `FIRESTORE_RULES_FRAGMENT.txt` là mẫu để gộp vào Rules hiện có **sau khi rà soát**, không ghi đè toàn bộ Rules cũ.

## 5. Kiểm tra backend không cần mở camera/USB

Trên máy tính có Internet, trong PowerShell, thư mục chứa `device_config.json`:

```powershell
python rfid_barcode.py --test-backend
```

Nếu thành công:

```text
OK: backend da xac thuc thiet bi may-quet-01
```

Nếu lỗi `401 device_not_authenticated`: sai `tokenSha256`/`deviceId`, quên bật `enabled` hoặc URL không đúng. Nếu `404 store_not_found_or_not_authorized` sau quét thẻ: thiếu `authorizedDevices` hoặc RFID không tìm thấy.

## 6. Nạp V5 cho ESP32

Trong project ESP-IDF hiện tại, **sao lưu** thư mục `main/`. Chép các file trong `main/` của ZIP sang `main/` dự án (ghi đè những file tương ứng), chú ý thay **cả `main/CMakeLists.txt`** để loại `firebase_client.c`. Không cần xóa các file `firebase_client.c/.h` cũ; chúng không còn được biên dịch.

Xóa các dòng cũ `CONFIG_STORE_WIFI_*`, `CONFIG_STORE_FIREBASE_*` nếu còn trong `sdkconfig` và `sdkconfig.defaults`; dùng menuconfig mới nếu phát sinh lỗi cấu hình. **Không gửi sdkconfig cũ của bạn cho người khác vì có thể chứa mật khẩu.** Nếu cấu hình cũ đã từng biên dịch mật khẩu vào firmware, bản V5 mới sẽ không tham chiếu nữa nhưng hãy cân nhắc luân chuyển mật khẩu cũ khi triển khai sản phẩm thật.

Dùng **ESP-IDF CMD** tại thư mục chứa `CMakeLists.txt`:

```cmd
idf.py reconfigure
idf.py build
idf.py -p COM4 flash monitor
```

Thấy `VERSION: RFID_MULTI_STORE_V5` và `V5: Cho Wi-Fi tu Python`. Thoát monitor bằng **Ctrl+]** (không để monitor mở đồng thời với Python).

Nếu RC522 không đọc được, kiểm tra dây: **SDA/SS=GPIO21**, SCK=GPIO18, MOSI=GPIO23, MISO=GPIO19, RST=GPIO22, 3.3V, GND.

## 7. Chạy Python, không cần nhập email/password Firebase

Trong PowerShell tại thư mục project gốc:

```powershell
python -m pip install -r requirements.txt
python rfid_barcode.py --port COM4
```

Nếu đã cài các thư viện Python/camera ở bản V4, có thể bỏ qua dòng pip. `pyzbar` trên Windows có thể cần thư viện ZBar DLL như dự án cũ.

Bây giờ **không có lệnh** `$env:STORE_FIREBASE_EMAIL` / `$env:STORE_FIREBASE_PASSWORD` nữa.

1. Máy tính kết nối Internet.
2. ESP32 kết nối USB COM4; **không mở idf_monitor**.
3. Đợi giao diện Python/mô hình và camera chạy xong.
4. Đưa thẻ `C79A0C03` đến RC522 rồi nhấc ra.
5. Python báo tìm thấy cửa hàng và gửi SSID; ESP32 kết nối Wi-Fi; GUI nhận sự kiện `ready`.
6. Đưa barcode tới camera; sản phẩm được lấy từ `stores/<storeDocumentId>/products` của cửa hàng đã chọn.

**Các dòng ESP32 thường gặp**:

```text
VERSION: RFID_MULTI_STORE_V5
@STORE:{"event":"scanning","generation":1,"rfid_uid":"C79A0C03"}
@WIFI:{"phase":"waiting_pc_credentials", ...}
STORE_RFID: Da nhan SSID=... (khong in mat khau)
STORE_RFID: WIFI_SWITCH: ... got_ip=YES
@STORE:{"event":"ready", ...}
```

**Chú ý:** ESP32 chỉ kết nối Wi-Fi cửa hàng; Firebase product lookup chạy trên máy tính qua Cloud Function. ESP32 không cần có internet riêng để Python tìm sản phẩm.

## 8. Sự cố thường gặp

| Hiện tượng | Nguyên nhân/cách xử lý |
|---|---|
| `FileNotFoundError: barcode_best.pt` | Đặt model cạnh `rfid_barcode.py` hoặc thêm `--model "duong-dan-model"` |
| `401 device_not_authenticated` | Chưa tạo đúng `devices/{deviceId}`, sai hash token, `enabled=false` |
| `404 store_not_found` | `stores.rfidId` không đúng/không chuẩn hóa, chưa có cửa hàng |
| `404 store_not_found_or_not_authorized` | Thiếu doc `authorizedDevices/{deviceId}` hoặc chưa bật enabled |
| `409 duplicate_rfid` | Nhiều cửa hàng dùng cùng UID; sửa cho duy nhất |
| `422 store_wifi_configuration_invalid` | Thiếu/sai `wifiSSID`, `wifiPassword`, hoặc tên store quá dài |
| `HTTP 403/404` chưa có code | URL backend sai hoặc chưa deploy function |
| `PermissionError(13) COM4` | Đóng `idf.py monitor`, các ứng dụng mở COM4; rút/cắm lại cáp nếu cần |
| `WIFI_SWITCH ... got_ip=NO` | Sai mật khẩu Wi-Fi, Wi-Fi chỉ 5GHz, bộ phát chặn thiết bị |
| Có `got_ip=YES` nhưng sản phẩm không hiện | Kiểm tra backend và subcollection `stores/{id}/products` chứa barcode dạng string |
| Lỗi RC522 | Kiểm tra 3.3V, GND, dây SPI/RST; tránh giữ thẻ liên tục trên đầu đọc |

## 9. Bảo mật/vận hành

- Cloud Function cần dự án có cấu hình **billing phù hợp**. Xem mức sử dụng/cảnh báo chi phí; `maxInstances:2` chỉ hạn chế số instance, không thay thế rate limiting hay ngân sách.
- Token thiết bị lưu trên PC, **không** trong firmware và không được cấp qua Hosting. Phân quyền NTFS cho file, bảo vệ máy tính/USB, không ghi token vào terminal/log. Mất token thì vô hiệu hóa `devices/{id}` và cấp token mới.
- `wifiPassword` được trả về PC của thiết bị đã được cấp quyền, rồi đi qua **USB serial không mã hóa**. Không in mật khẩu hoặc chia sẻ log thô có chứa lệnh `@CMD`.
- Admin SDK chạy trong Cloud Functions **bỏ qua Firestore Security Rules**; các kiểm tra trong `functions/index.js` là bắt buộc. Không tự ý bỏ `getDevice` và `storePermitted`.
- **Không triển khai endpoint công khai** không cần token với mục đích "dễ test"; UID RFID có thể bị sao chép.
- Tại website, khi muốn thêm nút chủ cửa hàng cấp quyền cho thiết bị, cần kiểm tra `ownerUid` và xác thực người dùng bằng Firebase Auth; không cho khách tự ý sửa subcollection này.

## 10. Kiểm tra mã nguồn đã thực hiện

- Python: `python -m py_compile pc/rfid_barcode.py pc/provision_device.py`.
- Node.js: `node --check functions/index.js`, `node --test functions/tests/helpers.test.js` (kiểm thử định dạng RFID/Wi-Fi/token).
- Chưa deploy vào Firebase của bạn hoặc build ESP-IDF/flash lên phần cứng thật trong môi trường tạo bản vá. Phải kiểm tra thực tế trong hệ thống của bạn.

## 11. (Tùy chọn) Thêm nút "Cho phép máy quét" trên website

File `web/authorize_device_example.js` là ví dụ cho website sử dụng Firebase Web SDK. Hàm `allowScanner(db, auth, storeDocumentId, deviceId)` cho chủ cửa hàng đã đăng nhập cấp quyền máy quét chung; hàm `revokeScanner(...)` thu hồi quyền. Trên form website, chủ cửa hàng chỉ nhập `device_id` (vd `may-quet-01`), **không yêu cầu token bí mật**. Phải gộp `FIRESTORE_RULES_FRAGMENT.txt` vào Rules hiện tại trước, đúng vị trí và không phá quyền quản lý của website. Chưa thể tích hợp trực tiếp nút vào giao diện web của bạn vì chưa có source website.

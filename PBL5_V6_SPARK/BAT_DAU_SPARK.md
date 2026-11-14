# Chạy V6 với Firebase Spark — bản sửa cần kiểm thử trên thiết bị thật

## 1. Luồng đúng và các giới hạn

- RFID chỉ định danh thẻ. Không chứa email, tên cửa hàng hoặc mật khẩu Wi-Fi.
- Laptop có Internet sẵn, nối ESP32 bằng USB. RC522 gửi UID -> Python đăng nhập tài khoản Firebase Auth RIÊNG CỦA MÁY QUÉT -> tra `rfidStores/{UID}` -> đọc cửa hàng được cấp quyền -> gửi Wi-Fi qua USB -> ESP32 báo IP -> Python mở tra cứu barcode.
- Barcode được truy vấn cùng `store_id` trong `stores/{store_id}/products`, giữ dạng chuỗi. Không tìm sản phẩm trên toàn hệ thống.
- Không phải gửi hai bản ghi RFID/barcode lên rồi mới tạo quan hệ: Python giữ cửa hàng hiện tại và gửi truy vấn barcode vào đúng đường dẫn đó.
- Hai cửa hàng có thể chung mạng Wi-Fi. SSID không xác định cửa hàng. Thông tin Wi-Fi phải là mạng 2.4 GHz thật, không captive portal.
- ESP32 chỉ đọc thẻ/kết nối Wi-Fi. Việc lấy dữ liệu Firebase vẫn chạy trên laptop. Đây KHÔNG phải thiết bị ESP32 độc lập cầm tay. Nếu cần bỏ laptop cần thiết kế lại camera, xử lý barcode, Internet ban đầu và âm thanh.
- Tên cửa hàng được nói khi ESP32 báo ready; chưa phải định vị địa lý/GPS và thẻ có thể bị sao chép.
- Không truy cập Firebase bằng URL Console. Spark hỗ trợ truy cập Auth/Firestore theo hạn mức; không có bảo đảm miễn phí không giới hạn. Bản này không dùng Cloud Functions, không yêu cầu deploy Functions hoặc Blaze.

## 2. Nguồn và thay đổi

Căn cứ GitHub TRUONGTHIHUE/pbl5, main commit 9a4993d702c065b92f13690c05109380bfb89330, và ZIP V6 do người dùng gửi.
- Giữ firmware V6, protocol USB 2 và model barcode_best.pt.
- `pc/spark_backend.py`: thêm REST client Auth + Firestore, dùng Security Rules thay vì Admin SDK.
- `pc/provision_spark.py`: nhập tài khoản máy quét một lần, lưu `pc/spark_config.json` trên PC; không lưu tài khoản chủ.
- `pc/app.py`: mặc định `--backend spark`, dùng spark_config.json. Backend Functions cũ vẫn chọn được bằng `--backend functions`.
- `pc/speaker.py`: đọc trạng thái/cửa hàng/sản phẩm bằng Windows System.Speech, cần giọng vi-VN thật sự có trong System.Speech. Không đọc mật khẩu Wi-Fi. Âm thanh đang đọc bị dừng khi phiên thay đổi.
- `firestore.spark.rules.example`: mẫu quyền scanner và chủ, cần rà soát với Rules website đang dùng trước khi Publish.

V6 trước chỉ GUI, V5 gốc chỉ tiếng beep. Chưa đủ cho người mù nếu chỉ dùng hai bản đó. Phần speech mới cũng chưa thử trên Windows/loa thật và chưa được đánh giá khả năng sử dụng cho người mù.

## 3. Thiết lập Firebase: làm một lần, không xóa dữ liệu cửa hàng

### 3a. Auth riêng cho máy quét

Chọn MỘT cách tạo tài khoản, không làm cả hai:

**Cách nhanh, bằng code mới:** sau khi bật Email/Password và có `.venv314`, chạy:
```
.venv314\Scripts\python.exe pc\register_scanner.py
```
Hoặc mở `DANG_KY_MAY_QUET.cmd`. Nhập API Key của đúng project, email RIÊNG cho máy quét và mật khẩu mới hai lần. Nhập DANGKY để đồng ý tạo Auth user. Script tự lấy Auth UID và tạo `pc/spark_config.json`. Sau đó đi thẳng đến bước 3b cấp quyền và 3c Rules; KHÔNG chạy provision_spark.py lần nữa. Nếu EMAIL_EXISTS, dùng cách tài khoản đã có bên dưới và provision_spark.py.

**Cách làm trong Console, hoặc tài khoản đã có:**
Firebase Console -> Build -> Authentication -> Sign-in method -> bật Email/Password.
Authentication -> Users -> Add user: tạo một email/mật khẩu riêng cho máy quét. Dùng địa chỉ email bạn quản lý, không dùng tài khoản chủ cửa hàng và không dùng mật khẩu mẫu công khai.
Copy UID của tài khoản vừa tạo, dưới đây gọi là SCANNER_AUTH_UID.
Không dùng ID `may-quet-01` cũ thay cho UID này trừ khi thực sự trùng UID Auth.

### 3b. Đăng ký thiết bị, cấp quyền và ánh xạ RFID
Firestore Data:

```
devices/SCANNER_AUTH_UID
    enabled: true                boolean

stores/askccukcywOrZMT9dn6B/authorizedDevices/SCANNER_AUTH_UID
    enabled: true                boolean

rfidStores/C79A0C03
    storeId: "askccukcywOrZMT9dn6B"     string
```

`rfidStores` là collection mới ở gốc, KHÔNG phải subcollection trong stores. Tạo document ID bằng UID thẻ chuẩn hóa, viết hoa, không dấu cách. Đây là bảng chỉ đường, không phải bản sao mật khẩu.
Kiểm tra lại document ID thực tế trong Console, không gõ theo ảnh nếu chưa chắc chữ hoa/thường.
Document cửa hàng giữ `rfidId: "C79A0C03"`, `storeName`, `ownerUid`, `wifiSSID`, `wifiPassword` đúng dữ liệu thật.
Sản phẩm giữ ở `stores/ID/products/ID_SAN_PHAM`; `barcode` là string đúng bao bì. Bốn barcode mẫu chỉ dùng thử dữ liệu, không phải mã hàng thật.

Mỗi thẻ có đúng một mapping. Khi đổi RFID trên website phải cập nhật mapping trong Console. Nếu có hai cửa hàng lưu cùng rfidId, phải sửa dữ liệu; bản Spark không có quyền quét toàn database để tự phát hiện mọi UID trùng. Mapping duy nhất xác định cửa hàng, và client/Rules kiểm tra rfidId khớp.
Không cần tokenSha256 cho tài khoản scanner Spark; các thiết bị V5/V6 Functions cũ có thể giữ nguyên.

### 3c. Rules (quan trọng)
Copy Rules hiện tại ra bản sao trước. Đối chiếu `firestore.spark.rules.example` với Rules hiện tại. Chỉ Publish sau khi giữ đúng các quyền website đang cần.
Không chạy deploy Functions. Không dùng `allow read, write: if true`.
Không để rule rộng khác cấp thêm quyền ngoài mẫu, vì các allow trùng nhau được OR.
Mẫu hỗ trợ website ownerUid, products và authorizedDevices như ảnh; chưa biết toàn bộ Rules/collection của website thật nên không được coi file mẫu là bản thay thế đã xác minh cho website đó.
`devices` và `rfidStores` chỉ admin tạo trong Console. Website chủ có thể cấp quyền qua authorizedDevices, không tự sửa mapping global ở mẫu này.

### 3d. API Key
Project settings -> General -> Your apps -> ứng dụng Web -> SDK setup/config -> lấy `apiKey`.
API Key không phải quyền quản trị hay mật khẩu; quyền đọc do Auth + Rules quyết định. Không tải service-account JSON.

## 4. Chạy Python 3.14 trong CMD của VS Code

Mở đúng root của bộ mới (nơi có main/, pc/, models/). Có thể dùng .venv314 đã cài của bộ V6 cũ bằng đường dẫn đầy đủ, hoặc tạo mới:

```
py -3.14 -m venv .venv314
.venv314\Scripts\python.exe -m pip install -r pc\requirements.txt
.venv314\Scripts\python.exe pc\provision_spark.py
```

Nhập Project ID, Web API Key, UID Auth scanner, email và mật khẩu scanner khi chương trình hỏi. Mật khẩu không hiện khi gõ. Không gửi file spark_config.json lên chat/GitHub. Windows cần giới hạn quyền NTFS cho file này; mode 0600 không tự bảo đảm NTFS ACL.

```
.venv314\Scripts\python.exe pc\app.py --test-backend
.venv314\Scripts\python.exe pc\app.py --test-rfid C79A0C03
```

Kết quả cần: BACKEND_OK, sau đó STORE_OK và WIFI_CONFIG_RECEIVED. Lệnh test-rfid chưa kết nối Wi-Fi trên ESP32.
- missing config: chạy provision_spark.py.
- HTTP400: kiểm tra tài khoản scanner/API key/Email Password enabled.
- scanner_uid_mismatch: UID trong config khác UID đăng nhập, không dùng UID chủ.
- HTTP403 store_not_authorized: kiểm tra Rules, device enabled, grant và mapping. Nếu API bị tắt/restricted API key cũng có thể 403; xem cấu hình Console, không tự mở dữ liệu.
- 404: kiểm tra đường dẫn, project ID và mapping. Mapping không tồn tại có thể bị Rules trả 403 thay vì 404 để không tiết lộ dữ liệu.
- rfid_mapping_store_mismatch: mapping và rfidId cửa hàng không khớp.

## 5. ESP32 và Wi-Fi

Firmware vẫn là V6. Nếu đã nạp đúng PBL5_UNIFIED_V6 thì không cần nạp lại vì bản sửa này không đổi firmware.
Nếu chưa nạp: ESP-IDF Terminal có đúng 5.5.5 (main/idf_component.yml hiện pin ==5.5.5):

```
idf.py --version
idf.py set-target esp32
idf.py build
idf.py -p COM4 flash monitor
```

Build chưa được xác minh bằng SDK thật trong lần sửa này. Không bỏ qua lỗi build. Sau khi thấy version V6, Ctrl+] đóng monitor.

CMD thường:
```
.venv314\Scripts\python.exe pc\app.py --port COM4 --wifi-only
```
Quét thẻ -> hiện đúng STORE01/SSID và IP. Đừng mở Serial Monitor cùng Python.
Cùng mạng -> action reused; đổi SSID/password -> reconfigured. IP chỉ xác nhận Wi-Fi, không khẳng định ESP32 có Internet.
Sau đó đóng cửa sổ và chạy:
```
.venv314\Scripts\python.exe pc\app.py --port COM4
```
Quét thẻ rồi đưa barcode thật vào camera. Có thể nhập barcode thủ công để tách lỗi dữ liệu khỏi lỗi camera.

## 6. Âm thanh và nghiệm thu người mù

Bật loa/tai nghe. Chương trình mặc định bật speech Windows, chỉ dùng giọng có Culture vi-VN trong System.Speech. Không có thì hiện thông báo, KHÔNG coi là âm thanh hoạt động.
Kiểm tra trong Windows PowerShell:
```
Add-Type -AssemblyName System.Speech
(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name; $_.VoiceInfo.Culture.Name }
```
Một số giọng Windows/Narrator không được System.Speech thấy. Nếu không có vi-VN cần cài giọng tương thích hoặc thay TTS; chưa được dùng thiết bị này như một trợ cụ đã hoàn chỉnh.
Dùng `--no-speech` chỉ để debug.

Nghiệm thu thật: thẻ đúng/sai, hai cửa hàng chung Wi-Fi, cùng barcode khác sản phẩm, quyền bị thu hồi, tắt router, rút USB, đổi thẻ lúc đang tra, camera hàng thật, giọng Việt, thao tác của người dùng. Ghi kết quả thật, không lấy test giả lập làm chứng nhận.

## 7. Bảo mật và phạm vi

Tài khoản scanner được xác thực nhưng đọc được Wi-Fi của mọi cửa hàng đã cấp quyền. Bảo vệ PC và USB. Thẻ RFID một mình không cấp quyền. Thu hồi bằng devices/UID.enabled=false hoặc grant.enabled=false.
Bản này giữ mô hình nhiều chủ, không lưu mật khẩu chủ, không service-account key trên PC. Chưa có cơ chế onboarding mapping trên website; admin làm trong Console. Chưa ghi lịch sử quét, chưa cập nhật kho/bán hàng. Không điều khiển website Firebase thật trong lần sửa này.

## 8. Chạy kiểm thử Rules tại máy phát triển (không bắt buộc để sử dụng)

Cần Node và Java 21, chỉ dùng project demo trong emulator, không chạy với project thật:
```
cd tests\rules
npm install
npm test
```

Kết quả lần sửa này: 24 kiểm tra Firestore Emulator đạt. Mẫu Rules được kiểm thử với schema trong fixture, KHÔNG phải Rules đang deploy của website thật. Những dòng PERMISSION_DENIED trong log là các ca cố tình thử truy cập trái quyền. File firebase.json mặc định rỗng để tránh deploy nhầm. Config Functions cũ đã chuyển sang firebase.functions.legacy.json.

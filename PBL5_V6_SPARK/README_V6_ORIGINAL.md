# PBL5 UNIFIED V6 — ESP32 · RFID · Wi-Fi · Barcode · Firebase

**Bộ mã nguồn thống nhất để tiếp tục kiểm thử; không phải bản đã được chứng nhận chạy thành công trên phần cứng.**

Đây là bản sao phát triển từ repository `TRUONGTHIHUE/pbl5`, nhánh `main`, commit
`9a4993d702c065b92f13690c05109380bfb89330` ngày 11/11/2026.
Không có thay đổi nào được đẩy lên GitHub hoặc triển khai vào Firebase trong lần bàn giao này.

## Bắt đầu ở đâu?

1. Đọc [hướng dẫn Windows](docs/WINDOWS_SETUP.md).
2. Cài backend/đăng ký thiết bị theo [hướng dẫn Firebase](docs/FIREBASE_SETUP.md), chỉ khi bạn quyết định triển khai.
3. Nạp **firmware V6** và chạy **Python V6** trong bộ này; không ghép với V3/V4/V5.
4. Thử `--wifi-only` trước. Sau đó đóng cửa sổ này và chạy ứng dụng đầy đủ để dùng camera.
5. Đối chiếu [kiểm thử nghiệm thu trên thiết bị](docs/HARDWARE_ACCEPTANCE.md).

Mã mới dùng protocol **v2**, firmware báo `PBL5_UNIFIED_V6`, backend export `deviceApiV6`.
Tên thư mục V6 và số protocol 2 là hai loại phiên bản khác nhau.

## Luồng thực sự được triển khai trong code

```text
RC522 → UID RFID → ESP32 → USB Serial → Python
                                         ↓ Internet của laptop
                                HTTPS backend deviceApiV6
                              xác thực token + quyền cửa hàng
                                         ↓
                       đúng store ID + owner UID + cấu hình Wi-Fi
                                         ↓ USB
                           ESP32 nhận cấu hình trong RAM
                                         ↓
                     giữ mạng cũ nếu cấu hình giống và còn sống,
                     hoặc chuyển mạng nếu SSID/mật khẩu thay đổi
                                         ↓
                      đúng cửa hàng + Wi-Fi có IP → cho quét barcode
                                         ↓
                     YOLO vùng barcode + pyzbar giải mã chuỗi
                                         ↓
                  products của đúng stores/{storeDocumentId}
```

Laptop phải có Internet trước. Python/backend, không phải firmware, thực hiện truy vấn Firebase.
**ESP32 có IP không chứng minh ESP32 truy cập Internet/Firebase.**
Không triển khai SoftAP, không tạo Wi-Fi từ tên tùy ý; hồ sơ phải lưu cấu hình mạng thật.

Các cửa hàng thử nghiệm được phép cùng SSID/mật khẩu Wi-Fi phòng trọ.
Cửa hàng phân biệt bằng RFID và document ID. Cùng Wi-Fi không làm dữ liệu sản phẩm bị gộp.

## Cấu trúc

```text
PBL5_UNIFIED_V6/
  CMakeLists.txt               # root ESP-IDF, không còn là bản vá thiếu root
  sdkconfig.defaults          # phần cứng; không chứa SSID/pass
  partitions.csv              # ESP32 4 MB; factory app, không có OTA
  main/                       # firmware + policy Wi-Fi
  pc/                         # giao diện, camera, Serial, backend client, provisioning
  models/barcode_best.pt      # model gốc, bytes được đối chiếu Git blob
  functions/                  # backend Node.js + kiểm thử + công cụ audit dữ liệu
  firebase.json               # codebase pbl5-device, chỉ Functions
  .firebaserc                 # project quanlycuahang-afb59, không phải bí mật
  firestore.rules.example    # mẫu để xem xét/gộp, KHÔNG tự deploy
  web/store_helpers.js        # ví dụ tích hợp website, không phải website hoàn chỉnh
  tests/                      # test Python, C policy, firmware với SDK giả lập, GUI
  scripts/
  docs/
  evidence/                   # kết quả chạy test và đối chiếu nguồn
  .github/workflows/          # workflow đề xuất, chưa chạy trên GitHub
```

## Lệnh dùng thường xuyên

Từ root project, sau khi đã tạo `.venv`, cài thư viện và cấu hình backend:

```powershell
.\.venv\Scripts\python.exe pc\app.py --test-backend
.\.venv\Scripts\python.exe pc\app.py --test-rfid "CD 4B 1E 03"
.\.venv\Scripts\python.exe pc\app.py --port COM4 --wifi-only
```

`--test-rfid` chỉ kiểm tra backend, không kết nối Wi-Fi trên ESP32.
Không mặc định `CD4B1E03` là thẻ duy nhất hoặc là RFID đúng của document đã biết.
Dùng UID thực tế của từng thẻ; `C79A0C03` là một UID khác từng xuất hiện trong log trước.

Khi Wi-Fi đã qua kiểm thử, đóng ứng dụng Wi-Fi-only rồi chạy:

```powershell
.\.venv\Scripts\python.exe pc\app.py --port COM4
```

Ứng dụng đầy đủ đã có toàn bộ bước Wi-Fi; không cần chạy thêm chương trình Wi-Fi riêng.
Không mở `idf.py monitor`, Python khác hoặc Arduino Serial Monitor cùng lúc.

## Chính sách Wi-Fi và phiên làm việc

- STA + `WIFI_STORAGE_RAM`. Cấu hình nhận qua USB, không hardcode và không ghi vào `sdkconfig`.
- Chỉ giữ kết nối khi **SSID và password cùng giống**, liên kết còn hoạt động, có IP,
  và SSID thực tế khớp. Không chỉ so sánh SSID.
- Đổi RFID luôn xóa lựa chọn/kết quả sản phẩm cũ trước khi gọi backend.
- Wi-Fi sai/mất, Serial mất, ESP reset, backend lỗi: barcode không được tiếp tục bằng cửa hàng cũ.
- Khi mạng trở lại, trạng thái phiên/link mới làm các phản hồi cũ mất hiệu lực.
- Mở lại Python: bắt tay bằng client ID mới, firmware cấp generation mới;
  nếu còn UID cuối trong RAM thì tự phân giải lại và kiểm tra quyền, không tin mù quáng phiên cũ.
- Mật khẩu không in ra log. Giao diện che mặc định, có thể hiện tạm 15 giây.
- Xác nhận Wi-Fi không đồng nghĩa xác nhận quyền vĩnh viễn: backend kiểm tra token/quyền
  lại mỗi lần lấy sản phẩm. Mất quyền thì chương trình chặn phiên.

## Những gì đã được xác minh

Xem [biên bản kiểm thử](docs/TEST_REPORT.md) và các file `evidence/`.

- Python: 32 test qua, trong đó có HTTP loopback Python ↔ Node với dữ liệu giả.
- Node: 23 test qua.
- C policy: 14 assertion qua trên GCC máy chủ.
- Actual firmware controller code: 8 nhóm kịch bản qua với API ESP/FreeRTOS **giả lập**.
- Tk GUI smoke test qua bằng Serial/backend giả.
- ZBar thật đọc được mã EAN13 từ ảnh tạo thử, giữ số 0 đầu.
- Model được giữ nguyên bytes/hash; **chưa chạy suy luận YOLO bằng model này**.

**Chưa build/link bằng ESP-IDF 5.5.5**, chưa có test Firebase thật,
USB Windows, camera thật, RC522 và Wi-Fi thật trên ESP32.
Không được diễn giải các test trên là “hệ thống đã chạy end-to-end trên thiết bị”.

## Phạm vi và bảo mật

Backend Cloud Functions cần Blaze để triển khai. Việc project từng hiển thị Spark
không cho biết trạng thái billing hiện nay; người quản trị kiểm tra trong Console.
Chi phí và các bước triển khai có trong `docs/FIREBASE_SETUP.md`.

Không có account chủ cửa hàng, mật khẩu Wi-Fi thật, device token thật hoặc service-account key
trong bộ mã này. File `pc/device_config.json` được sinh trên máy của bạn và phải giữ riêng.
Các chuỗi mật khẩu/token trong tests là dữ liệu giả lập rõ ràng, không dùng để vận hành.

Nguồn và những thay đổi: [AUDIT](docs/AUDIT.md).
Giao thức và timeout: [PROTOCOL](docs/PROTOCOL.md).

# Kiểm tra repository và thay đổi V6

## 1. Mốc nguồn và phương pháp

Repository: https://github.com/TRUONGTHIHUE/pbl5

Mốc được đọc:
- Nhánh: `main`.
- Commit: `9a4993d702c065b92f13690c05109380bfb89330`.
- Thời gian commit: `2026-11-11T09:13:30Z`.
- Message: `Update code PBL5 RFID and ESP_IDF`.
- Danh sách branch trả về chỉ có `main`.
- Lịch sử trả về một root commit, `parents: []`. Không có lịch sử nhiều commit
  để kết luận “lỗi này được sửa từ commit A sang commit B”.

Đã đọc metadata/history/Git tree và các file qua kết nối GitHub.
`git clone` trong container không thành công vì DNS của container không phân giải
`github.com`. Không trình bày thao tác này như một lần clone thành công.

Để có bytes làm việc, đối chiếu Git blob SHA-1 của file trong các ZIP đính kèm với
Git tree từ repo: 21 file V5 và 5 file thư mục cũ khớp. Python cũ thực tế khớp bytes
của bản vá V4 đính kèm, không phải Python cũ hơn trong ZIP gốc.
Manifest đầy đủ: `evidence/source_manifest.json`.
Model gốc cũng được xác minh bằng Git blob và SHA-256.

Đường dẫn nguồn:
```text
ESP_IDF_RC522_FIREBASE_v5_5/ESP_IDF_RC522_FIREBASE_v5_5/
ESP_IDF_RC522_FIREBASE_v5_5/ESP_IDF_RC522_FIREBASE/

RFID_MULTI_STORE_V5_patch/RFID_MULTI_STORE_V5/
```

Đã làm việc trên bản sao. Không push, không commit vào remote, không deploy,
không đọc/ghi dữ liệu riêng tư Firebase thật.

## 2. README, code thực tế và bằng chứng kiểm thử không phải một thứ

| Thành phần | README/chú thích nói gì | Code/tree thực tế | Kết luận |
|---|---|---|---|
| Thư mục cũ | README mô tả chương trình cũ hơn; docstring Python ghi V3 | Python mở GUI V4, đọc 4 biến Firebase và đăng nhập email/password, lọc ownerUid | Tài liệu không khớp code hiện tại |
| Thư mục cũ | Trông như một project ESP-IDF | Git tree có root CMake/model/Python nhưng không có main/ được track | Không đủ để build độc lập từ phần đã track |
| V5 | README nói rõ đây là bản vá | Có main/pc/functions, không có CMakeLists.txt root | Không được coi ZIP V5 là project build độc lập |
| V5 Wi-Fi | Lấy cấu hình rồi kết nối | Mỗi lần đều stop/set_config/start | Chưa tối ưu trường hợp hai cửa hàng cùng Wi-Fi |
| V5 backend | Xác thực thiết bị, nhiều chủ | Token hash và authorizedDevices đã có trong code | Giữ lại nguyên tắc, không ghi sai là “V5 thiếu xác thực” |
| V5 RFID | Yêu cầu rfidId HEX chữ hoa không dấu phân cách | Chuẩn hóa UID đầu vào, nhưng query equality trên dữ liệu lưu | `"CD 4B 1E 03"` không tự khớp `CD4B1E03` nếu chưa sửa dữ liệu |
| V5 test | Có kiểm thử logic và chú thích chưa thử thật | Test dùng mock, không chứng minh cloud/hardware | Không suy diễn đã deploy/chạy thực tế |

## 3. Lỗi hoặc thiếu sót đã xử lý

### Cấu trúc và phiên bản

Tạo một root project đầy đủ: CMake, main, pc, functions, model, cấu hình mẫu,
test và hướng dẫn. Firmware V6/protocol2 và Python V6 đi cùng nhau.
Backend dùng function mới `deviceApiV6`; không tự thay thế function V5 đang có.

Không sao chép `sdkconfig` chứa dữ liệu người dùng, build output hoặc token thực tế.

### Wi-Fi

V5 luôn cấu hình lại mỗi lần. V6 tách `wifi_policy.c` để so sánh đầy đủ
SSID/password và kiểm tra liên kết/IP thực tế trước khi giữ mạng.
SSID giống nhưng password khác phải chuyển/cấu hình lại.
RFID/store ID vẫn xác định cửa hàng độc lập với mạng.

Firmware mới dùng controller một chủ sở hữu state, callback không chờ mạng;
hủy lựa chọn cũ trước khi phân giải thẻ mới. Không fallback vào dữ liệu cửa hàng cũ.

Mất Wi-Fi làm `ready=false`, ngừng barcode, tăng dấu mốc liên kết;
có reconnect/backoff và trạng thái lỗi rõ. Một lần có IP không chứng minh Internet.

### Phiên, reset và dữ liệu trả muộn

V5 chủ yếu dùng generation nên reset ESP32 hoặc mở lại Python có thể tái sử dụng
số generation. V6 thêm:
- `boot_id`: đổi khi ESP khởi động.
- `client_id`: đổi khi mở lại Serial/Python.
- `generation`: đổi mỗi lần chọn thẻ/retry.
- epoch Python và `link_seq`/link epoch: phân biệt phiên và lần mất/nối mạng.

Kết quả Wi-Fi, product và khung hình chỉ áp dụng khi đúng stamp hiện tại.
Phản hồi lỗi/thành công của thẻ trước không ghi đè GUI thẻ sau.
Kết quả product còn kiểm tra store ID và barcode của chính yêu cầu.

### Python và camera

Tách Serial, backend và camera/inference khỏi GUI.
Có `--wifi-only`, manual barcode và lỗi camera tách khỏi chức năng Wi-Fi.
Đường dẫn model mặc định là root/models/barcode_best.pt, không phụ thuộc thư mục
đang đứng khi gọi script bằng đường dẫn.

Khi mở lại Python trong lúc ESP đang chạy, handshake mới yêu cầu kiểm tra backend
lại cho UID cuối. Không dùng trực tiếp store cũ chỉ vì firmware từng báo ready.

### Backend và dữ liệu

Giữ token hash, per-store ACL, scoped products, duplicate RFID/barcode, barcode string.
Bổ sung owner UID, version/project handshake, giới hạn/validation dữ liệu,
response identity để Python chống lẫn phiên.
Tách application service thuần khỏi adapter Firestore để test trực tiếp.

Thêm audit legacy dữ liệu, mặc định chỉ đọc.
Không tự sửa Firestore thật. Incoming UID được chuẩn hóa; stored rfidId
phải chuyển sang dạng canonical trước khi runtime equality query.
Không giả vờ “runtime tìm được mọi biến thể dữ liệu cũ” bằng một full scan không giới hạn.

### Website/Rules

Repo không có toàn bộ website quản lý để tích hợp giao diện thật.
`web/store_helpers.js` là module ví dụ phải được gọi từ form website.
`firestore.rules.example` là mẫu cần đối chiếu/gộp; không được deploy tự động.
Không coi website hay Rules emulator đã được kiểm thử.

## 4. Phần V5 đã có và được kế thừa về thiết kế

Token thiết bị riêng, so hash an toàn, kiểm tra authorizedDevices; không tài khoản
cá nhân chủ cửa hàng trong PC/ESP; query sản phẩm theo subcollection cửa hàng;
phát hiện duplicate; dùng chuỗi barcode; không in password.
V5 cũng đã chọn `WIFI_STORAGE_RAM` — V6 không phải lần đầu bổ sung tính năng RAM.

## 5. Giới hạn và việc chưa xác minh

Xem `TEST_REPORT.md`. Đặc biệt:
- Test C dùng stub không phải build ESP-IDF hoặc proof ABI.
- Không có endpoint/token thật để kiểm tra backend của project.
- Model bytes đúng nguồn không chứng minh model chạy hoặc nhận diện chính xác.
- Workflow CI chỉ là file được cung cấp, chưa chạy trên GitHub.
- Không có lockfile npm sinh từ cài đặt thật trong container; người dùng chạy npm install,
  kiểm tra dependency và giữ package-lock sau khi cài thành công.
- Chưa kiểm thử Rule bằng Firebase Emulator.
- Chưa đánh giá throughput, stress test hay đảm bảo vận hành production.

## 6. Nguồn trực tiếp

- Commit: https://github.com/TRUONGTHIHUE/pbl5/commit/9a4993d702c065b92f13690c05109380bfb89330
- V5 main: https://github.com/TRUONGTHIHUE/pbl5/blob/9a4993d702c065b92f13690c05109380bfb89330/RFID_MULTI_STORE_V5_patch/RFID_MULTI_STORE_V5/main/main.c
- V5 backend: https://github.com/TRUONGTHIHUE/pbl5/blob/9a4993d702c065b92f13690c05109380bfb89330/RFID_MULTI_STORE_V5_patch/RFID_MULTI_STORE_V5/functions/index.js
- Các hash/file còn lại: evidence/source_manifest.json.

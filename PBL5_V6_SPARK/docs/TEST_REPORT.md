# Biên bản kiểm thử — PBL5 UNIFIED V6

**Mốc kiểm tra: 13/11/2026. Đây không phải biên bản nghiệm thu hệ thống thật.**

## 1. Môi trường thực sự dùng

Container Linux, Python 3.13.5, Node.js v22.16.0, GCC 14.2.0, Tk/Xvfb.
Có ZBar/pyzbar và thư viện tạo ảnh thử. Không có ESP-IDF 5.5.5/Xtensa toolchain,
không có Firebase CLI/Cloud SDK dependencies đã cài cho triển khai.
Không nối ESP32, RC522, USB Windows, webcam hoặc router của người dùng.

Các lệnh Windows sử dụng Python3.11 trong hướng dẫn là môi trường dự kiến cho người dùng;
không coi test trên Python3.13/Linux là đã kiểm tra Python3.11/Windows.
Model `.pt` được đối chiếu bytes/hash, chưa dùng để chạy YOLO inference.

## 2. Kết quả đã chạy

| Lớp | Kết quả | Thực chất |
|---|---|---|
| Python compile | PASS | Kiểm tra cú pháp các module |
| JavaScript syntax | PASS | Node --check; không đồng nghĩa deploy được |
| Python unittest | **32 PASS, 0 skip** trong môi trường bàn giao | Controller, protocol, provisioning, camera logic giả, HTTP local, synthetic decoder |
| Node test | **23 PASS** | Application service/data audit và repository adapter giả |
| C policy | **14 assertion PASS** | GCC máy chủ, module policy thật |
| Controller firmware | **8 nhóm kịch bản PASS** | main.c thật với ESP/FreeRTOS API stub; không phải ESP-IDF |
| Tk GUI | PASS | Fake backend/Serial + manual barcode, password mask/reveal |
| ZBar synthetic | PASS, nằm trong32 Python tests | ZBar thật giải mã ảnh EAN13 tạo thử, giữ số0 đầu |
| HTTP Python ↔ Node | 5 test PASS, nằm trong32 Python tests | Socket HTTP loopback thật, application service thật, DB in-memory giả |
| ESP-IDF build/link | **CHƯA CHẠY** | Thiếu SDK/toolchain; không có binary ESP mới được xác minh |
| Firebase/Firestore thật | **CHƯA CHẠY** | Không endpoint/token/quyền đã xác minh; không deploy |
| Camera + YOLO model thật | **CHƯA CHẠY** | Không webcam, không runtime Ultralytics trong môi trường kiểm thử |
| ESP32/RC522/Wi-Fi/DHCP thật | **CHƯA CHẠY** | Không phần cứng |
| Firebase Rules Emulator | **CHƯA CHẠY** | Rules chỉ là mẫu cần review/merge |
| GitHub Actions | **CHƯA CHẠY** | Chỉ cung cấp workflow, không push/kích hoạt |

Không cộng các dòng lồng nhau thành nhiều test độc lập: 5HTTP + syntheticZBar
đã nằm trong số32Python. Các8nhóm firmware là kiểm thử giả lập host.

Bằng chứng:
- `evidence/all_checks.txt`: lần chạy tổng hợp mới nhất.
- `evidence/python_tests.txt`, `node_tests.txt`, `native_c_tests.txt`,
  `firmware_host_tests.txt`, `gui_tests.txt`.
- `evidence/gui_mock.png`: ảnh GUI với dữ liệu giả; không phải ảnh cửa hàng/Firebase thật.
- `evidence/source_manifest.json`: provenance nguồn.
- `models/SHA256SUMS`: checksum model, không phải điểm số nhận diện.

## 3. Đối chiếu yêu cầu kiểm thử

| Yêu cầu | Đã kiểm tra bằng gì | Còn phải thử thật |
|---|---|---|
| RFID hợp lệ | Node resolve và HTTP Python→Node | RC522 đọc thẻ thật + Firestore thật |
| RFID không tồn tại | Node/HTTP trả store_not_found | Kiểm tra database triển khai |
| RFID trùng | Node trả duplicate_rfid, migration phát hiện normalized collision | Audit database hiện tại |
| Device chưa có grant | Node/API deny, Python clear store | ACL thật |
| Hai store cùng Wi-Fi | C policy + actual firmware host assert không stop/start; controller đổi store | Quan sát reuse_count/switch_count và IP trên board |
| Cùng barcode ở hai store | HTTP local trả hai product riêng, adapter query scoped | Database thật/camera |
| Barcode không có trong store | API not_found và GUI state | Nhập/quét barcode trên hệ thống thật |
| Barcode trùng trong store | API duplicate, không chọn product đầu | Dữ liệu thật |
| Barcode số0 đầu | Validation/query string + ZBar ảnh synthetic | Nhãn hàng/camera thực |
| Sai password | Giả lập failed/timeout, no fallback store | Authentication trên router thật |
| Mất/nối Wi-Fi | Host firmware/drop/IP events + controller link epoch | Tắt/bật AP, DHCP/reason code thực |
| Đổi thẻ khi backend cũ đang chạy | Controller loại late resolve/product/camera result | Tạo độ trễ mạng thật |
| ESP reset | Boot nonce và reused generation giả lập | Nút EN/reset vật lý |
| Mở lại Python | New client/gen, fresh resolve trong test | Driver Windows/reset khi mở COM |
| Rút/cắm USB | Controller invalidation/reconnect state | Pyserial/driver/cổng thực |
| Không lộ password | Frame output/mask tests, không print secret trong code | Kiểm tra log thực tế/chính sách máy |

Sai password giả lập **không chứng minh** ESP-IDF sẽ báo mã reason cụ thể trên router
người dùng. Firmware nêu timeout/reason, không gán mọi lỗi cho mật khẩu.

## 4. Ý nghĩa của test C

`tests/test_wifi_policy.c` test logic thuần được build bằng GCC.
`tests/test_firmware_host.c` bao gồm implementation firmware với stub headers trong
`tests/esp_stubs/` để điều khiển sự kiện/thời gian/link.

Stub chỉ biểu diễn phần giao diện cần cho test, không phải bộ header SDK đầy đủ.
Test này giúp kiểm tra các nhánh control flow, nhưng không kiểm tra ABI, linker,
component resolution, FreeRTOS scheduling thực tế, heap, stack hoặc RF.

Cấu hình build dự kiến nhắm ESP-IDF5.5.5 và component rc5224.0.1.
Mốc xác minh tiếp theo phải là `idf.py build` bằng SDK thật, sau đó flash/monitor.

## 5. Chạy lại

```text
python scripts/run_checks.py
xvfb-run -a python tests/gui_smoke.py
```

Trên Windows có desktop, chạy `python tests\gui_smoke.py` không cần Xvfb.
Nếu thiếu GCC/ZBar thì test có thể skip; đọc tổng kết thực tế, không copy sốPASS trên
sang một môi trường chưa chạy.

GitHub workflow có bước build bằng container ESP-IDF nhưng **chưa chạy**.
Không lấy nội dung YAML làm bằng chứng build thành công.

## 6. Trạng thái bàn giao

Source đã có đầy đủ cấu trúc và implementation cho luồng yêu cầu, kèm test giả lập.
Chưa đủ bằng chứng để nói “đã chạy liền mạch trên ESP32 + camera + Firebase thật”.
Người dùng thực hiện checklist `HARDWARE_ACCEPTANCE.md` và ghi log tương ứng;
chỉ đánh PASS cho các bước thực sự đã quan sát.

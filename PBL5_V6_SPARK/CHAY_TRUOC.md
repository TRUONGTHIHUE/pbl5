# Đăng ký máy quét và chạy demo — làm theo thứ tự

Bản này phát triển từ GitHub TRUONGTHIHUE/pbl5 commit 9a4993d và bộ V6 bạn gửi, không thay GitHub/Firebase live. Không cần Blaze/Functions khi dùng mặc định Spark.

1. Giải nén sang thư mục riêng không dấu cách. Mở gốc có main/, pc/, models/ trong VS Code.
2. Firebase Console -> Authentication -> Sign-in method -> bật Email/Password. Lấy Web API Key của đúng project quanlycuahang-afb59 từ Project settings -> General -> Web app config.
3. CMD ở gốc:
```
py -3.14 -m venv .venv314
.venv314\Scripts\python.exe -m pip install -r pc\requirements.txt
.venv314\Scripts\python.exe pc\register_scanner.py
```
Chỉ dùng tài khoản mới RIÊNG cho máy quét. Script hỏi và tự lấy UID Auth, lưu cấu hình; không tự cấp quyền. Nếu đã có tài khoản, dùng pc/provision_spark.py. Không đăng ký lại khi đã có config.
4. Ghi lại UID Auth máy quét script in ra. Trong Firestore tạo:
```
devices/UID_AUTH_MAY_QUET
  enabled: true (boolean)
stores/askccukcywOrZMT9dn6B/authorizedDevices/UID_AUTH_MAY_QUET
  enabled: true (boolean)
rfidStores/C79A0C03
  storeId: "askccukcywOrZMT9dn6B" (string)
```
Copy đúng ID cửa hàng của bạn từ Console. rfidStores nằm ở GỐC, không ở trong stores.
5. Sao lưu Rules hiện tại; đối chiếu mẫu firestore.spark.rules.example. Chưa có Rules website hiện tại để bảo đảm thay thế hoàn toàn. Không Publish mù quáng; gửi Rules để rà soát nếu chưa rõ. Không mở quyền công khai.
6. Sau khi Rules và quyền sẵn sàng:
```
.venv314\Scripts\python.exe pc\app.py --test-backend
.venv314\Scripts\python.exe pc\app.py --test-rfid C79A0C03
```
7. Board cần firmware PBL5_UNIFIED_V6 (main/idf_component.yml pin ESP-IDF ==5.5.5). Nếu chưa có, build/flash theo BAT_DAU_SPARK.md. Đóng monitor.
8. Thử Wi-Fi:
```
.venv314\Scripts\python.exe pc\app.py --port COM4 --wifi-only
```
Đúng cửa hàng + SSID + có IP mới đạt bước Wi-Fi. Đóng cửa sổ đó, chạy đầy đủ:
```
.venv314\Scripts\python.exe pc\app.py --port COM4
```
9. Thêm sản phẩm thật, barcode dạng string. Quét thẻ rồi quét barcode; kiểm tra sản phẩm đúng cửa hàng. Speech cần giọng tiếng Việt trong Windows System.Speech và loa/tai nghe. Chưa có voice thì vẫn dùng được GUI nhưng chưa đạt yêu cầu người mù.

Đọc BAT_DAU_SPARK.md để xử lý lỗi, Rules, âm thanh và giới hạn. Không cần chạy lệnh firebase deploy của bộ V6 cũ. Không gửi spark_config.json cho người khác.

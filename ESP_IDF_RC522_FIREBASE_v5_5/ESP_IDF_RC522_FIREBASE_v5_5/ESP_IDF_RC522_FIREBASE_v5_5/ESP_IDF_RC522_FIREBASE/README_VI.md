# ESP-IDF 5.5.x: ESP32 + RC522 + Firebase

Dự án cho ESP32 thường (ESP32-WROOM/DevKit), theo phiên bản bạn dùng: ESP-IDF 5.5.5. Không dùng Arduino.

## Nối dây

| RC522 | ESP32 |
|---|---|
| SDA/SS | GPIO21 |
| SCK | GPIO18 |
| MOSI | GPIO23 |
| MISO | GPIO19 |
| RST | GPIO22 |
| 3.3V | 3V3 |
| GND | GND |
| IRQ | Không nối |

SDA/SS ở đây là chip select của SPI, không phải I2C. Nguồn 3.3V.

## Mở và cấu hình trên VS Code

1. Giải nén vào thư mục mới, ví dụ `D:\PBL5_RFID_IDF`. Mở thư mục có CMakeLists.txt bằng File > Open Folder. Không thay vào thư mục website Firebase.
2. Chọn ESP-IDF 5.5.5 trong extension ESP-IDF. Mở terminal bằng lệnh **ESP-IDF: Open ESP-IDF Terminal** từ Ctrl+Shift+P.
3. Chạy:

```bash
idf.py --version
idf.py set-target esp32
idf.py menuconfig
```

4. Trong menu **STORE RFID - Cau hinh du an**, điền Wi-Fi, email và mật khẩu đăng nhập WEBSITE. Wi-Fi phải có Internet (ESP32 thường dùng Wi-Fi 2.4 GHz). Không dùng mật khẩu tài khoản Google admin. API Key và Project ID đã điền theo website đang làm.
5. Lưu bằng S và thoát bằng Q. Build:

```bash
idf.py build
idf.py -p COM5 flash monitor
```

Thay COM5 bằng cổng thiết bị của bạn. Ctrl+] để thoát monitor. Có thể dùng nút Build/Flash/Monitor của extension thay terminal.

Component Manager tự tải `abobija/rc522` 4.0.1 qua main/idf_component.yml khi build lần đầu; máy tính cần Internet. Không cài MFRC522/ArduinoJson từ Arduino IDE.

Nếu thiếu cấu hình Wi-Fi/email/mật khẩu, vẫn đọc UID nhưng không gọi Firebase. Muốn test riêng RFID, bỏ chọn `Ket noi Firebase sau khi quet RFID` trong menuconfig.

## Gán thẻ cho cửa hàng

1. Nạp và quét: monitor hiện `UID THE: A1B2C3D4` (ví dụ).
2. Tạo cửa hàng trên website bản nhiều cửa hàng và nhập UID thực tế vào RFID. Hồ sơ đã có: sửa rfidId trong Firestore.
3. Đảm bảo hồ sơ nằm ở `stores/{documentId}`; trường `ownerUid` bằng UID tài khoản cấu hình trên ESP32. Nếu hồ sơ cũ chỉ có uid, đăng nhập website bản nhiều cửa hàng một lần để website tự bổ sung ownerUid.
4. Giữ Rules bản nhiều cửa hàng. Không cần sửa Rules để mở quyền công khai.
5. Tháo thẻ, quét lại. Khi thành công hiện tên, mã hiển thị và Document ID.

UID được chuẩn hóa sang HEX chữ hoa, 2 ký tự mỗi byte. Trường rfidId có thể chứa dấu cách, dấu : hoặc -; vẫn so khớp. Nhận UID dài 4, 7 hoặc 10 byte. Hai cửa hàng cùng UID trong tài khoản sẽ báo trùng và không chọn cửa hàng.

## Trạng thái và luồng

RC522 callback chỉ đọc UID và gửi queue. Firebase task chờ Wi-Fi, đồng bộ thời gian NTP, đăng nhập email/password, gọi Firestore REST qua HTTPS.

Truy vấn lọc `ownerUid == UID tài khoản`, chỉ tải storeName/storeId/rfidId, so UID trên ESP32. Không tải hoặc in mật khẩu Wi-Fi từ Firestore. Rules vẫn xác thực tài khoản.

Cửa hàng đã chọn được giữ khi tháo thẻ. Khi quét thẻ mới, cửa hàng cũ bị xóa ngay. Nếu thẻ mới không hợp lệ/lỗi mạng/trùng UID, không sử dụng nhầm cửa hàng cũ. Nếu quét thẻ khác khi HTTPS đang chạy, kết quả thẻ cũ bị bỏ; queue chỉ giữ lần quét mới nhất.

`store_get_current(store_info_t *out)` trả về bản sao cửa hàng đã chọn, có mutex. Barcode sau này dùng `out.document_id` để truy vấn `stores/{documentId}/products`. Project hiện chưa quét barcode hoặc lấy sản phẩm.

## Giới hạn cần biết

- Wi-Fi được cấu hình trước trong menuconfig; chưa tự lấy mạng theo thẻ.
- Chỉ nhận diện cửa hàng thuộc tài khoản ESP32 đăng nhập. Thiết bị chung cho nhiều chủ cửa hàng cần thiết kế cấp quyền/API riêng.
- Không ghi dữ liệu vào thẻ; gán UID trên website/Firestore.
- Phản hồi truy vấn tối đa 64 KiB để bảo vệ RAM. Nếu quá lớn sẽ báo lỗi, không chọn từ danh sách thiếu.
- Chứng chỉ dùng ESP-IDF certificate bundle, không bỏ xác minh TLS. Bật trong sdkconfig.defaults.
- Email/password Wi-Fi và website được lưu trong sdkconfig/firmware. Không chia sẻ sdkconfig hoặc firmware đã điền mật khẩu.
- Không xóa hoặc cập nhật dữ liệu cửa hàng qua ESP32; project chỉ đọc.

## Đọc lỗi

- Không có UID: kiểm tra nguồn 3.3V, GND và 5 dây tín hiệu.
- Chưa điền cấu hình: mở menuconfig, điền, build/flash lại.
- Chưa có IP: kiểm tra Wi-Fi 2.4 GHz và mật khẩu.
- Chưa đồng bộ giờ: mạng cần cho phép NTP; tháo/quét lại sau.
- INVALID_LOGIN_CREDENTIALS: sai email/mật khẩu website.
- HTTP 403: kiểm tra Rules và ownerUid.
- HTTP 401: token bị từ chối; lần quét sau đăng nhập lại.
- Database not found: kiểm tra Project ID và database `(default)`.
- Không tìm thấy thẻ: rfidId chưa đúng hoặc cửa hàng thuộc tài khoản khác.

## Kiểm tra trước khi giao

Đã kiểm tra logic chuẩn hóa UID và phân tích JSON Firestore bằng kiểm thử C trên máy chủ, gồm không tìm thấy, UID 7/10 byte, trùng UID và dữ liệu lỗi. Driver/API đối chiếu tài liệu và ví dụ của tác giả.

Chưa build toàn project bằng toolchain ESP-IDF 5.5.5 và chưa chạy trên phần cứng thật ở môi trường tạo file. Khi build trên máy bạn, gửi các dòng lỗi đầu tiên nếu có; che mật khẩu/token.

Nguồn API: https://github.com/abobija/esp-idf-rc522 ; https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-reference/protocols/esp_http_client.html ; https://firebase.google.com/docs/firestore/use-rest-api

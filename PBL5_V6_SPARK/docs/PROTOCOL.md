# Protocol v2 và state machine V6

Đây là mô tả implementation trong bộ V6, không phải bằng chứng thiết bị đã chạy.

## 1. USB

115200 baud, một JSON object trên một dòng UTF-8.
ESP → PC: `@STATE:`.
PC → ESP: `@CMD:`.
Giới hạn frame lệnh 2048 byte kể cả newline. Không echo/log lệnh chứa password.

Không dùng @STORE/@WIFI/@PRODUCT của bản V3/V4/V5 cho runtime V6.
Script mới phát hiện marker firmware cũ và yêu cầu nạp lại.

## 2. Bắt tay và định danh

PC tạo client_id HEX32 mỗi lần mở Serial. ESP tạo boot_id HEX16 khi boot.
generation tăng khi quét thẻ, retry hoặc client mới khôi phục UID cuối.
Python dùng thêm connection epoch, request stamp và link epoch.
Những giá trị này chống lẫn phiên, **không thay thế xác thực bảo mật backend**.

Bắt tay:
```text
@CMD:{"v":2,"command":"hello","client_id":"<HEX32>"}
```

Poll:
```text
@CMD:{"v":2,"command":"status","client_id":"<HEX32>"}
```

Lệnh cấp Wi-Fi chứa boot_id, generation, rfid_uid, store_id, store_name, owner_uid,
ssid, password và client_id. Không đưa frame đầy đủ chứa bí mật vào log.
Chỉ firmware đang chờ credential của đúng tuple mới nhận lệnh.

cancel/retry có client_id/boot_id/generation.
cancel xóa lựa chọn store; retry tạo một generation mới để lấy cấu hình lại.

## 3. Snapshot

Các giá trị dưới đây chỉ là minh họa:

```json
{
  "v": 2,
  "firmware": "PBL5_UNIFIED_V6",
  "boot_id": "0011223344556677",
  "client_id": "00112233445566778899aabbccddeeff",
  "generation": 2,
  "rfid_uid": "CD4B1E03",
  "store_id": "store-demo-b",
  "store_name": "Cua hang B",
  "owner_uid": "owner-example-b",
  "phase": "ready",
  "code": "",
  "ready": true,
  "wifi": {
    "connected": true,
    "ssid": "SSID-thuc-te",
    "ip": "192.168.1.20",
    "reason": 0,
    "action": "reused",
    "reuse_count": 1,
    "switch_count": 1,
    "link_seq": 1
  }
}
```

Không có password trong snapshot.

Cửa hàng mới có thể đang chờ backend trong khi `wifi.connected=true` của mạng
vật lý trước. Lúc này `ready=false`; **không được coi connected=true là cửa hàng đã sẵn sàng**.
Chỉ store_id đúng phiên + credentials mới đã được cấp + actual link/IP mới mở barcode.

## 4. Các phase chính

| phase | Ý nghĩa |
|---|---|
| idle | Chờ thẻ/client |
| waiting_credentials | Đã có RFID, chờ backend qua Python |
| switching | Đang dừng Wi-Fi để đổi cấu hình |
| connecting | Đang kết nối cấu hình mới |
| ready | Đúng cấu hình có IP, phiên được phép tra barcode |
| reconnecting | Mất mạng/đang nối lại; barcode bị chặn |
| wifi_failed | Lỗi/timeout kết nối, có retry, không dùng store cũ |
| backend_error | Backend từ chối hoặc timeout |
| credentials_timeout | Hết thời gian chờ cấp cấu hình |
| pc_disconnected | Hết lease client |

`wifi.action` là none/reconfigured/reused/reconnecting.
reason là mã sự kiện Wi-Fi ESP-IDF; không diễn giải mọi mã hoặc connect_timeout
thành chắc chắn “sai mật khẩu”.

## 5. Deadline trong implementation

- ESP chờ credential: 45 giây.
- Kết nối Wi-Fi mỗi chu kỳ: 25 giây.
- Chờ STOP event: 3 giây.
- Retry sau lỗi chu kỳ: 15 giây; retry nội chu kỳ có backoff giới hạn 16 giây.
- Lease PC: 15 giây không nhận lệnh hợp lệ thì xóa lựa chọn.
- Snapshot khoảng mỗi giây hoặc khi thay đổi; PC poll mỗi 2 giây.
- Python deadline resolve/product: 23 giây.
- Không có snapshot 7 giây: Python chặn dữ liệu và bắt tay lại.
- Serial worker không thấy snapshot hợp lệ 10 giây: đóng/mở lại cổng.
- GUI loại snapshot đã nằm trong hàng đợi quá 5 giây.
- Hiện mật khẩu GUI: tự che sau 15 giây.

Các deadline là giá trị code, không phải SLA hay kết quả timing được đo trên phần cứng.

## 6. HTTP backend

POST JSON qua HTTPS endpoint `deviceApiV6`.
Headers:
```text
Content-Type: application/json
X-Device-Id: <device_id>
Authorization: Bearer <device_token>
```

Không log Authorization hoặc request body.
Body luôn có `api_version:2` và action ping/resolve_store/lookup_product.

resolve_store trả:
```text
store.id, store.name, store.owner_uid, store.rfid_uid
wifi.ssid, wifi.password
```

lookup_product bắt buộc store_id và barcode string.
Response có store_id và barcode để Python đối chiếu identity.
status found/not_found/duplicate; duplicate không trả một product tùy ý.

Backend kiểm tra thiết bị và grant mỗi request cần store.
Có IP không tự cấp quyền backend; UID thẻ không phải mật khẩu xác thực thiết bị.

## 7. Khôi phục

Mở lại Python gửi client mới. ESP giữ UID cuối trong RAM nhưng cấp generation mới,
xóa lựa chọn và lấy cấu hình/authorization lại. Cùng cấu hình/mạng sống sẽ reuse.

Reset ESP sinh boot_id mới; phản hồi cũ cùng generation vẫn bị loại.
Mất Wi-Fi tăng dấu mốc link, kết quả barcode đang chờ bị bỏ.
Mất Serial xóa phiên Python; reconnect tạo client mới.
Retry hoặc quét RFID mới sẽ không lấy lại kết quả sản phẩm của phiên trước.

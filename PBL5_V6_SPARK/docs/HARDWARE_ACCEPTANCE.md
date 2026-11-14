# Checklist nghiệm thu trên hệ thống thật

Tất cả mục dưới đây đang **CHỜ NGƯỜI DÙNG THỬ**. Không phải kết quả đã chạy.

## A. Điều kiện trước khi thử

Build V6 thật bằng ESP-IDF5.5.5 thành công; đúng COM4; đóng monitor trước Python.
Laptop có Internet. Backend thực tế phản hồi đúng project/deviceApiV6.
Dữ liệu đã audit RFID canonical và barcode string.
Không quay/chụp mật khẩu hay token. Chỉ ghi firmware version, store ID, phase,
IP/reason/action/counter và kết quả sản phẩm không chứa bí mật.

Tạo/kiểm tra hai store thử A và B với RFID **khác nhau**, mỗi store có grant cho máy quét.
Có thể cùng owner hoặc khác owner. Cả hai lưu cùng SSID/password Wi-Fi trọ thật.
Trong products của mỗi store, tạo cùng barcode string `0012345678905`
nhưng name hoặc price khác nhau để nhìn rõ phạm vi truy vấn.
Không ghi đè sản phẩm vận hành; dùng bộ dữ liệu demo được chủ cho phép.

## B. Các bước và tiêu chí

| Mã | Thao tác | Chỉ đánh PASS khi |
|---|---|---|
| H01 | idf.py build, flash và mở monitor | Build/link thật OK; board báo PBL5_UNIFIED_V6, không reset loop |
| H02 | app.py --test-backend | BACKEND_OK đúng project/device |
| H03 | app.py --test-rfid UID_A | STORE_OK đúng A, nhận config; chưa kết luận ESP kết nối |
| H04 | Mở --wifi-only, quét A | Đúng store A, actualSSID/IP, ready=true |
| H05 | Quét B cùng Wi-Fi | Store B hiện đúng; action=reused; reuse_count tăng; switch_count không tăng vì lần quét này |
| H06 | Nhập barcode chung khi A/B lần lượt được chọn | Mỗi lần trả đúng product của store tương ứng, không cache A sang B |
| H07 | Nhập barcode chỉ tồn tại ở A trong khi chọn B | not_found, không tìm sang store A |
| H08 | Tạo duplicate barcode trong cùng store demo | Báo duplicate, không chọn product ngẫu nhiên; dọn dữ liệu thử sau đó |
| H09 | Dùng RFID chưa có store | Báo không tìm thấy, không giữ sản phẩm/cửa hàng cũ |
| H10 | Tạo normalized duplicate RFID ở hai store demo | Backend/audit báo trùng; không chọn cửa hàng đầu |
| H11 | Thu hồi grant máy quét ở store B | Chọn B bị từ chối; product request không được tiếp tục bằng quyền cũ |
| H12 | Sai password của store B nhưng SSID vẫn giống A | Phải cấu hình lại, không reuse chỉ vì SSID giống; timeout/lỗi rõ; barcode bị chặn |
| H13 | Sửa lại password B trên Firebase, nhấn Quét lại | Config mới về qua USB, kết nối lại; không nạp firmware |
| H14 | Tắt AP khi đang ready | UI ready=false, kết quả đang chờ bị vô hiệu hóa, không tra barcode |
| H15 | Bật lại AP | ESP nối lại/IP; đúng store được khôi phục, kết quả cũ không ghi đè |
| H16 | Đổi thẻ B trong lúc request A chưa xong | Chỉ phản hồi B có hiệu lực, không bật barcode bằng A |
| H17 | Nhấn EN/reset khi backend đang xử lý | Boot ID mới; credentials/product của boot cũ bị loại |
| H18 | Đóng/mở Python, giữ ESP hoạt động | Client/generation mới, xác thực backend lại; có thể reuse Wi-Fi, không tin store cũ mù quáng |
| H19 | Rút/cắm USB | Chặn phiên khi mất; reconnect tạo phiên mới; đúng COM và không cần dùng log cũ |
| H20 | Mở app đầy đủ và quét nhãn bằng camera | YOLO/pyzbar thật decode và trả đúng product, giữ barcode string |
| H21 | Đổi mật khẩu router thật và cập nhật Firestore | Retry/lần lấy config mới dùng mật khẩu mới, không sửa code |
| H22 | Backend/mạng laptop mất tạm thời | Timeout/backend error rõ; không hiển thị nhầm store/product trước |

H12 cố tình lưu mật khẩu sai là thao tác test có thể làm mất kết nối:
chỉ làm ở store demo và khôi phục ngay.
Router đổi password có thể làm laptop cũng mất Internet; kết nối lại laptop trước
khi yêu cầu backend cấp config mới. Không nhầm việc laptop mất mạng với lỗi firmware.

Để thử chuyển giữa **hai mạng thật khác nhau**, cần thêm AP/điểm phát tương thích.
Một AP đủ để kiểm tra H04/H05 và việc chuyển cấu hình password, nhưng không chứng minh
chuyển giữa hai SSID vật lý khác nhau.

## C. Thu log và đánh giá đúng

Monitor chỉ dùng trước khi chạy Python hoặc sau khi đóng Python, không tranh chấp COM.
Ứng dụng hiển thị store, trạng thái Wi-Fi, IP, action/counter. Log firmware mong đợi:

```text
PBL5: SCAN generation=... uid=...
PBL5: WIFI_READY store=... ip=... action=reconfigured
PBL5: WIFI_REUSED store=...
PBL5: WIFI_FAILED code=connect_timeout reason=...
```

Các dòng trên là mẫu, không phải log test thật.
Không gửi frame `@CMD` chứa password. Snapshot `@STATE` không có password.
Mã reason dùng để chẩn đoán; cần đối chiếu ESP-IDF đúng phiên bản, không tự suy
mọi reason là sai pass.

Mẫu ghi nhận:
```text
Ca: H05
Ngày/giờ:
Commit/version:
Thiết bị/COM:
Store A/B:
wifi.action:
reuse_count trước/sau:
switch_count trước/sau:
Kết quả: PASS / FAIL / CHƯA THỬ
Log/ảnh đã che thông tin:
```

Kết quả H04/H05 có IP là kiểm tra kết nối Wi-Fi, không phải kiểm tra Firebase từ ESP.
Firebase request hiện chạy trên laptop. Nếu yêu cầu đồ án sau này bắt ESP tự HTTP
lên server, đó là tính năng bổ sung cần code và ca test riêng.

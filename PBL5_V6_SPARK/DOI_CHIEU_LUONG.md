# Đối chiếu yêu cầu với nguồn GitHub và bản sửa

Nguồn GitHub TRUONGTHIHUE/pbl5 main 9a4993d702c065b92f13690c05109380bfb89330. Không push remote.

1. V5 gốc đã kết hợp RFID chọn store với barcode qua Python/Cloud Functions. Không phải RFID chứa mật khẩu. V5 chỉ beep.
2. V6 trước đã có kiểm soát phiên và tái sử dụng Wi-Fi, nhưng mặc định gọi Functions nên cần Blaze, chưa có speech.
3. Bản Spark sửa phía Python/Auth/Rules, giữ firmware V6/RC522/Wi-Fi/model. Mỗi store dùng grant scanner Auth UID và có mapping thẻ.
4. Website đang hiển thị dữ liệu, không phải API endpoint. Bản sửa không tự thay code website, không tự cập nhật Rules live.
5. Sản phẩm tra theo stores/{storeId}/products với barcode string. Barcode mẫu không thể đem quét bao bì thật trừ khi thay mã.
6. Điểm CHƯA đáp ứng thiết bị độc lập cho người mù: vẫn cần laptop Internet/USB/camera, speech dùng loa laptop và giọng Windows; không có GPS/định vị, không ghi lịch sử, không kiểm định khả năng sử dụng. ESP32 chưa trực tiếp truy vấn Firebase.
7. Khi chủ thay RFID, mapping rfidStores phải được admin cập nhật; chưa có giao diện tự onboarding mapping. Global duplicate RFID không được scan toàn database trong client Spark.
8. Không thể cam kết chạy toàn bộ chỉ từ test mock. Cần SDK build, thiết bị thật và đối chiếu Rules website trước Publish.

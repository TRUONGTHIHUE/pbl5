# Bảo mật và giới hạn

## Bí mật ở đâu?

Không hardcode Wi-Fi, token thật, owner password hoặc service-account key trong source.
`pc/device_config.json` chứa token máy quét, được tạo một lần trên PC.
Chỉ hash token nằm tại devices/{deviceId}. Website chủ không cần biết token gốc.
SSID/password cửa hàng lưu trong Firestore theo yêu cầu dự án, chỉ backend được
cấp quyền và owner hợp lệ mới được truy cập theo thiết kế.

Không coi UID RFID là cơ chế xác thực chống sao chép.
Backend phải kiểm tra device token và grant theo store trước khi trả mật khẩu.
Sản phẩm cũng kiểm tra quyền ở mỗi truy vấn.

## PC và USB là vùng tin cậy

Người có quyền đọc config trên PC có thể dùng token của máy quét.
Bảo vệ account Windows, NTFS ACL và không dùng PC dùng chung không kiểm soát.
Cờ tạo file 0600 trong Python không thay thế kiểm tra ACL thực tế trên Windows.

Password đi qua USB Serial không được mã hóa ở tầng ứng dụng.
Code không log secret và clear bộ đệm khi có thể; Python không bảo đảm zeroization
tuyệt đối đối với mọi bản sao chuỗi trong bộ nhớ.
Token và mật khẩu không được đưa vào screenshot, git history, issue, log debug hoặc Hosting.
Nút hiện mật khẩu chỉ dành người đang có quyền trên máy quét, mặc định che.

Backend HTTPS từ chối endpoint HTTP ngoài chế độ loopback test riêng.
Không theo redirect mang theo bearer token. Không bỏ TLS validation để “sửa lỗi”.

## Quyền cloud và Rules

Admin SDK không chịu Firestore Security Rules như web client.
Phân quyền ở functions/api.js và IAM runtime là bắt buộc.
HTTP endpoint có thể được gọi không qua Cloud IAM nhưng **application auth vẫn bắt buộc**.
Không bỏ token/authorizedDevices chỉ để demo nhanh.

Rules example chưa được kiểm thử emulator và chưa tích hợp website.
Không có Firestore entry trong firebase.json; chức năng deploy của bộ này không tự thay rules.
Kiểm tra broad allow ở rules cũ trước khi triển khai.
Không phân phối ADC/service-account key cho scanner runtime.

## Thu hồi

Vô hiệu hóa device hoặc grant để chặn request mới.
Nếu token lộ, cấp token mới và đổi hash ở Firestore.
Nếu Wi-Fi password từng được người không có quyền biết, thu hồi token không làm họ quên
mật khẩu; cân nhắc đổi password router và cập nhật hồ sơ.

## Không hứa production-ready

Có validation, giới hạn kích thước, timeout, maxInstances và secret-safe errors.
Chưa có kiểm thử tải, rate limiting phân tán, quản lý danh tính phần cứng chống trích xuất,
pentest hoặc nghiệm thu vận hành production.
Firestore read và Function invocation vẫn có thể tạo chi phí; xem billing guide.

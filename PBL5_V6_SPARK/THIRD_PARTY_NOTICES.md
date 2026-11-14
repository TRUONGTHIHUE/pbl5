# Nguồn và thành phần bên ngoài

Mã V6 được phát triển từ yêu cầu người dùng và đối chiếu repository:
https://github.com/TRUONGTHIHUE/pbl5
Baseline: 9a4993d702c065b92f13690c05109380bfb89330.

Model `models/barcode_best.pt` được sao chép nguyên bytes từ nguồn người dùng:
- Kích thước: 6.506.474 byte.
- Git blob: 7bd353817f65333ff00943008bee3b96d6a65b0e.
- SHA-256: 92a2a556adccb585dd9a1b2f61706b6c66368fae98f6f970101bbab8ebbed66d.

Không suy luận quyền sử dụng thương mại hoặc một giấy phép mới cho model/source gốc
chỉ từ việc repository công khai. Kiểm tra nguồn/giấy phép trước khi phân phối tiếp.

Các dependency được tải khi người dùng cài/build, có giấy phép riêng:
ESP-IDF, abobija/rc522, cJSON, pyserial, OpenCV, Ultralytics/Torch, pyzbar/ZBar,
Pillow, firebase-admin, firebase-functions và dependency bắc cầu.
Bộ này không phát hành lại SDK/compiler, thư viện hệ thống hoặc font.
Các test dùng ReportLab để tạo ảnh barcode tổng hợp, không chứa ảnh khách hàng.

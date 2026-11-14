# Kết quả kiểm tra bản Spark

- Python: 43 test chạy, 42 PASS, 1 SKIP (thiếu runtime tạo/giải mã ảnh thử ZBar). Gồm 9 test Spark mới và 2 test đăng ký tài khoản; các kiểm thử Spark dùng HTTP fake, không phải đăng nhập Firebase thật.
- Node logic V6: 23 PASS.
- C Wi-Fi policy: 14 assertion PASS; firmware host: 8 nhóm kịch bản PASS với API giả lập.
- Firestore Rules Emulator: 24 checks PASS bằng Java 21, firebase-tools, @firebase/rules-unit-testing. Không chạm dữ liệu live.
- Model SHA256: 92a2a556adccb585dd9a1b2f61706b6c66368fae98f6f970101bbab8ebbed66d, giống bộ gốc.
- Chưa build ESP-IDF 5.5.5, chưa flash board, chưa thử Windows speech hoặc live Auth/Firestore/camera/router.
- Chưa có full source website và Rules hiện tại để hợp nhất tự động.
- Các tài liệu V6 gốc trong docs/ được giữ để tham khảo, không chứng nhận bản Spark.

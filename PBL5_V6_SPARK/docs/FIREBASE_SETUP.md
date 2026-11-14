# Firebase V6: cấu hình, dữ liệu, quyền và triển khai

Project người dùng cung cấp: **quanlycuahang-afb59**.
Document đã biết: **stores/ctiYWZgSVACP7SH7QWp3**.

Trong lần bàn giao này **chưa xác minh nội dung hiện tại** của document đó, endpoint đang chạy,
Firestore Rules đang áp dụng hoặc gói billing hiện tại. Không có đọc/ghi Firebase thật,
không có deploy, không có dữ liệu bí mật người dùng trong test.

## 1. Spark, Blaze và chi phí

Cloud Functions có thể được thử bằng emulator, nhưng để triển khai functions lên Firebase
project phải ở **Blaze** theo tài liệu Firebase. Việc ảnh trước hiển thị Spark không chứng minh
project vẫn Spark hôm nay; kiểm tra Usage and billing bằng tài khoản quản trị.

Blaze không có nghĩa mỗi lần gọi đều bị tính tiền: có mức sử dụng miễn phí tùy dịch vụ,
nhưng **không đảm bảo demo luôn bằng 0 đồng**. Chi phí có thể đến từ thực thi Functions,
Firestore reads/storage, lưu artifact/container phục vụ deployment và lưu lượng mạng.
Mức thực tế phụ thuộc lượng dùng/vùng/chính sách hiện hành; không có cơ sở báo giá cố định
cho project này khi chưa có thống kê sử dụng.

Bộ code đặt minInstances=0, maxInstances=2, concurrency=10.
Đây là cấu hình tài nguyên, **không phải trần hóa đơn** và không thay thế rate limiting.

Tài liệu Firebase hiện phân biệt:
- Alerts-only budgets: gửi cảnh báo, không tự dừng dịch vụ.
- Spend cap budgets: có hỗ trợ cho một số dịch vụ, gồm Cloud Functions; có thể tạm dừng
  dịch vụ được chọn khi đạt ngưỡng. Không coi đó là giới hạn chung cho mọi chi phí
  Firestore/dịch vụ khác của project.

Kiểm tra mục Usage and billing, đặt cảnh báo/spend cap phù hợp trước khi tự deploy.
Không tự bật billing hay dùng tài khoản thanh toán thay người dùng.

Nguồn chính thức, được đối chiếu ngày 13/11/2026:
- https://firebase.google.com/docs/functions/get-started
- https://firebase.google.com/docs/functions/quotas
- https://firebase.google.com/docs/projects/billing/budget-alerts
- https://firebase.google.com/docs/projects/billing/spend-caps

## 2. Chuẩn bị dữ liệu cửa hàng

Collection `stores`, document ID là khóa định danh, không phải SSID.

Với document đã biết, kiểm tra/cập nhật qua Firebase Console:

```text
stores/ctiYWZgSVACP7SH7QWp3
  storeName:     <tên cửa hàng thật>             string
  ownerUid:      <UID chủ cửa hàng hiện có>      string
  rfidId:        <UID canonical của thẻ gắn store này> string
  wifiSSID:      <SSID Wi-Fi thật ở phòng trọ>   string
  wifiPassword:  <mật khẩu Wi-Fi thật>           string
```

Giữ nguyên ownerUid đúng; không thay bằng email, device ID hoặc một UID giả.
Backend trả `owner_uid` cho Python/ESP nhưng không dùng tài khoản chủ để đăng nhập.

SSID giới hạn 1–32 byte UTF-8. Bản triển khai này nhận password rỗng cho mạng mở,
hoặc WPA2 passphrase ASCII in được 8–63 ký tự / PSK64hex.
Không hỗ trợ đăng nhập captive portal/enterprise trong luồng này.

Hai store thử nghiệm có thể lưu cùng SSID/password thật.
Không cần tạo mạng mới, đổi router hoặc nạp lại firmware khi thêm store.
Mỗi thẻ chỉ gắn một store trong toàn hệ thống, không chỉ trong từng owner.

## 3. RFID cũ có dấu cách

Quy ước: HEX chữ hoa, bỏ khoảng trắng, dấu `:` và dấu `-`.
Chấp nhận UID 4/7/10 byte, tương ứng 8/14/20 ký tự HEX.

```text
"CD 4B 1E 03" → "CD4B1E03"
"cd:4b:1e:03" → "CD4B1E03"
"C79A0C03"    → "C79A0C03"   (một thẻ khác)
```

Không tự gán CD4B1E03 vào document đã biết nếu chưa xác nhận đúng thẻ của store đó.
Backend chuẩn hóa **UID đầu vào**, nhưng dùng equality query đối với `rfidId` đã lưu.
Do đó phải chuẩn hóa dữ liệu cũ trước; không có full scan mọi cửa hàng mỗi lần quét.

Nếu hai store lưu `CD4B1E03` và `CD 4B 1E 03`, chúng là cùng UID sau chuẩn hóa.
Cần giải quyết collision trước khi dùng; không chọn tùy ý store đầu tiên.

Với ít dữ liệu, sao lưu và sửa tay trong Console sau khi kiểm tra toàn bộ cửa hàng.
Với nhiều dữ liệu, dùng công cụ audit bên dưới. Website cần gọi helper chuẩn hóa
trước khi lưu; chỉ chép file helper vào repo không tự làm form website gọi nó.

## 4. Barcode là string

Sản phẩm nằm đúng đường dẫn:

```text
stores/{storeDocumentId}/products/{productId}
  barcode: "0012345678905"    string
  name: "Sản phẩm thử A"     string
  price: 10000              number hoặc theo schema hiện có
```

Cùng barcode được phép có ở hai store khác nhau và trả sản phẩm khác nhau.
Hai product cùng barcode trong **cùng store** bị báo duplicate, không chọn đại.

Không chuyển barcode sang integer để query.
Nếu trước đây đã lưu numeric, số 0 đầu có thể đã mất; không thể suy ra lại chỉ
từ con số. Sửa theo mã thật trên nhãn/dữ liệu gốc.
Code không tự chuyển numeric thành một chuỗi giả định.

## 5. Deploy backend — chỉ thực hiện khi bạn quyết định

Dùng PowerShell tại **root bộ V6**, không ở trong main.
Không chạy firebase init ghi đè tùy tiện website cũ: bộ này đã có firebase.json riêng.
Nếu cần tích hợp vào một repo website khác, giữ codebase `pbl5-device`,
giữ những function/codebase đang có và không ghi đè cấu hình Hosting/Rules.

Cài Node.js22/Firebase CLI, đăng nhập bằng tài khoản quản trị có quyền deploy:

```powershell
cd D:\PBL5_UNIFIED_V6
npm install -g firebase-tools
firebase login
firebase projects:list
cd functions
npm install
npm test
cd ..
```

`npm install` tạo package-lock theo phiên bản thực tế cài được; giữ lockfile cho các lần sau.
Container bàn giao chưa cài npm dependencies cloud, nên không kèm lockfile giả.

Khi đã kiểm tra billing và sẵn sàng triển khai:

```powershell
firebase deploy --only functions:pbl5-device --project quanlycuahang-afb59
```

Lệnh chỉ nhắm codebase trong firebase.json. Function export là **deviceApiV6**,
không phải deviceApi của V5. Sao chép **URL thật được Firebase CLI trả về**,
không tự đoán URL là đã hoạt động.

`firebase deploy --only hosting` không triển khai backend này.
Nếu CLI đề nghị xóa function khác ngoài dự định, dừng và kiểm tra codebase/project.
Không dùng `--force` để bỏ qua cảnh báo.

Nguồn codebase:
https://firebase.google.com/docs/functions/organize-functions?gen=2nd

Endpoint HTTP cho phép request đi tới ứng dụng (`invoker: public`), nhưng API vẫn
bắt buộc token thiết bị và ACL trong application code. Không phải endpoint lấy
mật khẩu công khai chỉ cần biết RFID.

Admin/server SDK bỏ qua Firestore Security Rules nên không bỏ phần kiểm tra quyền
trong `functions/api.js`. Quyền IAM của runtime cũng cần được cấu hình phù hợp.
Nguồn: https://firebase.google.com/docs/firestore/security/rules-conditions

## 6. Đăng ký máy quét một lần

Tại root project:

```powershell
.\.venv\Scripts\python.exe pc\provision_device.py --device-id may-quet-01 --endpoint "URL_HTTPS_THAT_CUA_DEVICEAPIV6" --project quanlycuahang-afb59
```

Thay URL mẫu bằng URL thật. Chương trình sinh token ngẫu nhiên,
ghi vào `pc/device_config.json` và chỉ in hash `tokenSha256`.

Không chạy lại để ghi đè file đang dùng. Nếu đã có config cần giữ token,
sao lưu an toàn và cập nhật đúng endpoint/project; không tạo token mới rồi quên
cập nhật hash trên Firestore.

Tạo document trong Console bằng quyền quản trị:

```text
devices/may-quet-01
  enabled: true                   boolean
  tokenSha256: <64 ký tự hash>     string
```

**Không dán token gốc vào Firestore**, không đưa config lên GitHub/Hosting.

Mỗi store muốn sử dụng máy quét phải có:

```text
stores/{storeDocumentId}/authorizedDevices/may-quet-01
  enabled: true                   boolean
```

Ví dụ với document đã biết:

```text
stores/ctiYWZgSVACP7SH7QWp3/authorizedDevices/may-quet-01
```

Document ID của grant phải bằng device_id, không phải email hoặc UID RFID.
Thêm store mới chỉ cần nhập dữ liệu/grant, không sửa code và không nạp lại ESP.

Thu hồi thiết bị: devices/{id}.enabled=false hoặc thu hồi grant ở store.
Việc thu hồi chặn request backend tiếp theo, không làm người đã biết mật khẩu Wi-Fi
“quên” mật khẩu. Nếu lộ bí mật, cần thay token và cân nhắc đổi mật khẩu Wi-Fi.

## 7. Kiểm tra backend thật sau khi deploy

```powershell
.\.venv\Scripts\python.exe pc\app.py --test-backend
.\.venv\Scripts\python.exe pc\app.py --test-rfid "UID_THAT"
```

Hai lệnh kiểm tra HTTPS, API version, project, device token, store/grant và cấu hình.
Không cần camera hoặc Serial, không in mật khẩu.
Chỉ khi chính bạn chạy thành công mới ghi vào biên bản “Firebase thực tế PASS”.
Không coi test loopback trong evidence là kết quả Firebase thật.

## 8. Audit dữ liệu — mặc định chỉ đọc

Công cụ admin riêng, không phải dependency runtime của máy quét.
Chỉ chạy trên máy quản trị có Application Default Credentials và IAM phù hợp.
Không phát service-account JSON cho máy quét/ESP32.

Ví dụ đã có Google Cloud CLI:

```powershell
gcloud auth application-default login
cd D:\PBL5_UNIFIED_V6\functions
node tools\audit_data.js --project quanlycuahang-afb59 --check-products
```

Lệnh chỉ đọc, không sửa dữ liệu. Nó đọc rfidId/barcode, không tải/in wifiPassword.
Audit nhiều document vẫn phát sinh Firestore reads; cân nhắc chi phí.

Kết quả cần xem: RFID invalid, normalized duplicate, kế hoạch cập nhật,
barcode numeric và duplicate theo từng store.
Không gửi dump Firestore chứa bí mật vào issue/chat công khai.

Sau backup, xử lý collision và chủ động cho phép sửa, mới dùng:

```powershell
node tools\audit_data.js --project quanlycuahang-afb59 --apply --confirm-project quanlycuahang-afb59
```

Công cụ từ chối áp dụng nếu có RFID invalid/duplicate.
Mỗi update có precondition updateTime để tránh ghi đè chỉnh sửa đồng thời.
Nhiều batch **không atomic toàn bộ**; nếu một batch lỗi, có thể các batch trước đã được áp dụng.
Thực hiện trong cửa sổ bảo trì, audit lại sau đó.
Công cụ không tự sửa barcode numeric hoặc suy ra số 0 đã mất.

Không lệnh audit/apply nào được chạy vào project thật trong lần bàn giao này.

## 9. Rules và website

`firestore.rules.example` là mẫu để đối chiếu/gộp, không phải bản đã tích hợp website.
`firebase.json` không khai báo Firestore deployment để tránh ghi đè rules hiện có.
Rules mẫu giữ document devices ngoài quyền client; store/product/grant theo owner.

Kiểm tra các match rộng trong rules cũ: một allow rộng ở match khác có thể vẫn cho
truy cập dù đã thêm rule hẹp. Đừng mở read công khai để sửa HTTP403.

`web/store_helpers.js` phải được nhập và gọi từ form thật. Chưa có source website đầy đủ
trong repo nên chưa xác nhận UI/create/update/rules của website chạy đúng.

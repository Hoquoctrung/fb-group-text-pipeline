# Challenges — baseline for Phase 0 + Phase 1

Các mục có trạng thái `pending` chưa phải số liệu đo được. Sau khi chạy pipeline trên dữ liệu được phép, cập nhật bằng chứng từ metrics/log; không tự điền số liệu giả.

| Thách thức | Biểu hiện trong dự án | Bằng chứng (số liệu/log) | Giải pháp đã làm | Rủi ro còn lại | Nếu làm production |
|---|---|---|---|---|---|
| 1. Truy cập nhóm | Có thể gặp login wall/checkpoint | pending — chưa chạy crawl | Có giới hạn phiên và dừng khi phát hiện dấu hiệu chặn | Heuristic không thể nhận diện mọi trạng thái | Theo dõi trạng thái và quy trình xin phép chính thức |
| 2. Quyền riêng tư | Bài viết có thể chứa PII | Unit test scrubber; số lượng thực tế pending | HMAC author, scrub email/SĐT/URL | Regex không bao phủ mọi dạng PII | Duyệt thủ công + công cụ DLP phù hợp |
| 3. Thiên lệch feed | Feed có thứ tự/hiển thị do nền tảng kiểm soát | pending — chưa thu thập | Ghi nhận nguồn và phạm vi phiên | Không thể khẳng định bao phủ toàn nhóm | Thiết kế lấy mẫu được phê duyệt và công bố giới hạn |
| 4. Schema không công bố | Payload có thể đổi | TODO(real-sample) — chưa có mẫu thật | Parser tổng quát và fixture tự tạo | Parser có thể trả về 0 bài | Quản lý fixture đã ẩn danh, regression tests |
| 5. DOM thay đổi | UI có thể thay đổi | DOM fallback chưa triển khai theo §0b | Ưu tiên passive GraphQL response | Không có fallback nếu parser không khớp | Chỉ thêm fallback khi được phép và có test |
| 6. Dữ liệu nhiễu | Emoji, teencode, URL, thiếu dấu | Synthetic fixture có nhiễu; số liệu thực tế pending | Bộ dữ liệu synthetic để kiểm thử | Chưa đo tỷ lệ nhiễu thật | Thống kê quality metrics trước phân tích |
| 7. Bài trùng | Repost có thể xuất hiện | Synthetic fixtures có một số nội dung lặp; đo thật pending | Checkpoint chống trùng ID | Chưa deduplicate theo nội dung | Bổ sung dedup ở preprocessing phase |
| 8. Thiếu metadata | Timestamp hoặc author có thể không có | parse tests; tỷ lệ null thực tế pending | Parser bỏ node không đủ trường tối thiểu | Có thể mất bài hợp lệ | Đo missing-field rates trên mẫu đã duyệt |
| 9. Định danh tác giả | ID thô có thể định danh người dùng | Privacy tests; crawl thực tế pending | HMAC-SHA256 với salt ở môi trường | Salt phải giữ bí mật và ổn định | Quản lý secret an toàn, giới hạn quyền truy cập |
| 10. Dữ liệu nhập lỗi | CSV/JSONL có thể sai định dạng | `ImportCollector.errors` ghi dòng lỗi | Bỏ qua dòng lỗi và báo lại | Cần xem xét lỗi trước khi phân tích | Schema/versioning và quarantine hàng lỗi |
| 11. Tái lập | Thời gian/nguồn có thể khác | Seed 42 cho synthetic | Fixture cố định và test | Dữ liệu thật không thể tái tạo hoàn toàn | Lưu manifest, package versions và thời điểm chạy |
| 12. Bảo mật repository | Có thể vô tình commit secret hoặc dữ liệu | `.gitignore` + secret scanning hook | Loại `.env`, `.auth/`, data và debug khỏi Git | `.gitignore` không ngăn file đã tracked | Kiểm tra `git status`, secret scanning và lịch sử Git |
| 13. Giới hạn tốc độ | Cuộn quá nhanh có thể gây tác động không mong muốn | delay cấu hình 3–8 giây | Giới hạn phiên/tốc độ | Tuân thủ điều khoản vẫn là trách nhiệm người chạy | Throttle chặt và phê duyệt trước vận hành |
| 14. Dữ liệu synthetic khác thực tế | Synthetic không phản ánh đầy đủ phân phối thật | source=`synthetic` trong từng record | Gắn nhãn nguồn và chỉ dùng demo/test | Không dùng synthetic làm kết quả thực nghiệm | Báo riêng nguồn và không trộn dữ liệu mà không ghi rõ |
| 15. Quy mô lưu trữ | Storage benchmark chưa được triển khai | pending — thuộc phase Store | Chưa triển khai theo đúng thứ tự phase | Chưa có số đo hiệu năng storage | Benchmark SQLite và Parquet/DuckDB ở 1k/10k |

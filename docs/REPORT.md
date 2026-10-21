# Báo cáo — bản khung Phase 0 + Phase 1

> Các số liệu thực nghiệm sẽ được sinh tự động ở các phase sau. Không điền số giả. Các đoạn nhận định để Trung tự viết sau khi xem dữ liệu.

## §2. So sánh 5 kỹ thuật thu thập (Bảng 1)

| Kỹ thuật | Định nghĩa ngắn | Dùng khi | Ưu điểm | Nhược điểm | Hiện thực trong phạm vi 48 giờ |
|---|---|---|---|---|---|
| File import | Đọc dataset CSV/JSONL có sẵn | Có dữ liệu được phép sử dụng | Ổn định, nhanh, tái lập | Phụ thuộc nguồn dữ liệu | `ImportCollector` — triển khai |
| Web scraping | Trích xuất nội dung từ HTML/DOM đã render | Cần dữ liệu hiển thị trên trang | Linh hoạt, không cần API | Dễ vỡ khi UI đổi | Không triển khai DOM parser trong phạm vi tối thiểu |
| Crawling | Duyệt liên tục qua nội dung với checkpoint và giới hạn tốc độ | Cần thu thập nhiều bài theo feed | Có thể lấy nhiều bản ghi trong phiên | Phụ thuộc trạng thái truy cập/schema | `PlaywrightCollector` tối thiểu — triển khai có điều kiện |
| API | Gọi giao diện lập trình chính thức để truy vấn dữ liệu có cấu trúc | Nền tảng cung cấp API và quyền truy cập phù hợp | Dữ liệu có cấu trúc, hợp đồng rõ hơn | Quyền/phạm vi API có thể bị giới hạn hoặc thay đổi | Chỉ mô tả lý thuyết; không demo code API theo §0b |
| Streaming | Nhận và xử lý dữ liệu liên tục theo thời gian | Bài toán yêu cầu xử lý gần thời gian thực | Độ trễ thấp, xử lý tăng dần | Đòi hỏi vận hành, xử lý sự kiện trễ và trùng | Chỉ mô tả lý thuyết; không có `stream_sim` theo §0b |

## Trạng thái triển khai

- Import/Synthetic: có thể chạy offline.
- Playwright/GraphQL: bản tối thiểu; chưa xác thực bằng mẫu phản hồi Facebook thật.
- API, streaming, DOM fallback: không triển khai code trong phạm vi 48 giờ.
- Các phần số liệu/hình về preprocessing, biểu diễn, storage và visualization: cập nhật ở các phase tương ứng.

## Nhận định

<!-- TRUNG VIẾT: sau khi chạy pipeline và kiểm tra dữ liệu được phép sử dụng. -->

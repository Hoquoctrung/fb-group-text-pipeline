# Báo cáo — khung Phase 0 đến Phase 4

> Không điền số liệu giả. Mọi số đo biểu diễn và lưu trữ phải lấy từ file metrics sinh bởi CLI. Phần **Nhận định** để Trung tự viết sau khi xem dữ liệu được phép sử dụng.

## §2. So sánh 5 kỹ thuật thu thập (Bảng 1)

| Kỹ thuật | Định nghĩa ngắn | Dùng khi | Ưu điểm | Nhược điểm | Hiện thực trong phạm vi 48 giờ |
|---|---|---|---|---|---|
| File import | Đọc dataset CSV/JSONL có sẵn | Có dữ liệu được phép sử dụng | Ổn định, nhanh, tái lập | Phụ thuộc nguồn dữ liệu | `ImportCollector` — triển khai |
| Web scraping | Trích xuất nội dung từ HTML/DOM đã render | Cần dữ liệu hiển thị trên trang | Linh hoạt, không cần API | Dễ vỡ khi UI đổi | Không triển khai DOM parser trong phạm vi tối thiểu |
| Crawling | Duyệt liên tục qua nội dung với checkpoint và giới hạn tốc độ | Cần thu thập nhiều bài theo feed | Có thể lấy nhiều bản ghi trong phiên | Phụ thuộc trạng thái truy cập/schema | `PlaywrightCollector` tối thiểu — chưa xác minh schema thật |
| API | Gọi giao diện lập trình chính thức để truy vấn dữ liệu có cấu trúc | Nền tảng cung cấp API và quyền truy cập phù hợp | Dữ liệu có cấu trúc, hợp đồng rõ hơn | Quyền/phạm vi API có thể bị giới hạn hoặc thay đổi | Chỉ mô tả lý thuyết; không demo code API theo §0b |
| Streaming | Nhận và xử lý dữ liệu liên tục theo thời gian | Bài toán yêu cầu xử lý gần thời gian thực | Độ trễ thấp, xử lý tăng dần | Đòi hỏi vận hành, xử lý sự kiện trễ và trùng | Chỉ mô tả lý thuyết; không có `stream_sim` theo §0b |

## §4. Biểu diễn văn bản (Bảng 3 — sinh số liệu khi chạy CLI)

- **BoW:** `CountVectorizer` trên `tokens_nostop`, n-gram (1, 2), đầu ra sparse `.npz` và vocabulary JSON. Số chiều, mật độ/thưa và kích thước artifact nằm trong `data/metrics/represent.json`.
- **TF-IDF:** `TfidfVectorizer(sublinear_tf=True)` trên cùng trường token đã làm sạch. Công thức khái quát: \(\mathrm{tfidf}(t,d)=\mathrm{tf}(t,d)\times\mathrm{idf}(t)\). Kết quả top-term theo TF và theo TF-IDF cùng nằm trong metrics để so sánh; không điền kết quả trước khi CLI chạy.
- **E5:** `intfloat/multilingual-e5-small` trên `text_clean`, tiền tố `query: ` và chuẩn hóa L2. Import thư viện và tải model là tùy chọn; nếu lỗi thì BoW/TF-IDF vẫn được lưu, và metrics phải ghi trạng thái E5 bị bỏ qua.
- **Đánh giá:** `fbpipe label-sample` tạo mẫu phân tầng tại `data/labels/to_label.csv`. Sau khi điền nhãn người, `fbpipe label-eval` tính macro-F1 out-of-fold. Khi chưa có nhãn tay, luật heuristic tạo proxy labels; mọi kết quả có `proxy_labels=true` và không được diễn giải như ground truth.

**Nhận định — Trung tự viết:** So sánh macro-F1, số chiều, độ thưa, kích thước và thời gian từ `data/metrics/represent.json` + `data/metrics/label_eval.json`. Phân biệt rõ kết quả nhãn tay với kết quả proxy.

## §5. Lưu trữ (Bảng 4 — sinh số liệu benchmark)

| Backend | Truy vấn / đặc trưng | Giới hạn cần nêu |
|---|---|---|
| SQLite + FTS5 | Upsert theo `doc_id`, lọc ngày, đếm theo tháng, full-text search | FTS5 là chỉ mục văn bản; vẫn chịu giới hạn của một file database cục bộ |
| Parquet | Lưu dữ liệu dạng cột, quét text/ngày/tháng bằng pandas/pyarrow | Không có full-text index; scan không tương đương FTS5 |
| PostgreSQL, MongoDB, Elasticsearch, DuckDB | Chỉ mô tả lý thuyết | Không triển khai trong phạm vi rút gọn Phase 4 |

`fbpipe bench-storage --n 1000 --iterations 20` tạo dữ liệu bootstrap có ID mới trong thư mục tạm, đo SQLite và Parquet rồi ghi `data/metrics/bench_storage.json`. Đây là bản sao benchmark có nhiễu dựa trên Silver, không phải 1.000 bài Facebook độc lập; cold first-pass cũng không bảo đảm đã xoá cache hệ điều hành.

**Nhận định — Trung tự viết:** Dựa trên số liệu latency, throughput và kích thước trong JSON metrics để giải thích vì sao SQLite/Parquet đủ dùng ở quy mô hiện tại và khi nào cần backend khác.

## Trạng thái triển khai

- Import/Synthetic: chạy offline; Playwright/GraphQL chưa được xác minh bằng mẫu phản hồi Facebook thật.
- Preprocess S0–S11: đã có mã và test.
- Represent/label/store: mã và unit tests đã được thêm; cần chạy lại toàn bộ Ruff/pre-commit, Parquet integration, E5 (nếu cài model) và benchmark trên máy phát triển.
- Các biểu đồ F01/F03/F06/F07/F09/F10/F11/F13/F14/F15 chưa được sinh trong Phase 3–4 rút gọn này; thuộc phần Viz sau.

## Nhận định tổng kết

<!-- TRUNG VIẾT: dựa trên số liệu thật được phép sử dụng; không đưa dữ liệu synthetic/benchmark clone thành kết quả từ Facebook. -->

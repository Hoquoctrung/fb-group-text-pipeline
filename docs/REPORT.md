# Báo cáo — khung Phase 0 đến Phase 4

> Không điền số liệu giả. Mọi số đo biểu diễn và lưu trữ phải lấy từ file metrics sinh bởi CLI. Phần **Nhận định** để Trung tự viết sau khi xem dữ liệu được phép sử dụng.

> **Báo cáo tự động:** [`REPORT_generated.md`](REPORT_generated.md) — được tạo bằng `fbpipe report`; lệnh không ghi đè tài liệu thủ công này.

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


## Nguồn dữ liệu & giới hạn

- **Nguồn trong demo**: SyntheticCollector tạo 200 bản ghi synthetic và gắn provenance là `source=synthetic`. Đây là dữ liệu kiểm thử, không phải bài đăng lấy từ Facebook.
- Nếu thay bằng dữ liệu nhập, báo cáo phải ghi đúng N bản ghi theo `data/metrics/import.json` và số bản ghi hợp lệ/không hợp lệ trong `data/metrics/preprocess.json`; không gán nguồn Facebook khi provenance không chứng minh điều đó.
- **Nhãn**: khi chưa có nhãn tay, label-eval dùng nhãn proxy theo luật (`proxy_labels=true`). Điểm số chỉ có ý nghĩa chẩn đoán, không phải ground truth.
- **Crawl live chưa xác minh**: chưa có bằng chứng end-to-end từ phiên Facebook được phép và phản hồi thật đã ẩn danh; fixture tự dựng không chứng minh collector/parser hoạt động với dữ liệu live.
- **Benchmark 1k**: bản benchmark tạo các dòng clone có nhiễu/ID mới từ Silver. 1.000 dòng benchmark không đồng nghĩa 1.000 bài độc lập.

## Hạn chế & hướng phát triển

| Thành phần | Ý tưởng lý thuyết / trường hợp phù hợp | Lợi ích kỳ vọng | Hạn chế / trạng thái |
|---|---|---|---|
| MongoDB | NoSQL dạng document, hợp với schema lồng như bài + bình luận | Linh hoạt schema, mở rộng theo cụm tùy kiến trúc | **Không triển khai**; cần service, index và contract tests |
| Elasticsearch | Inverted index/BM25 cho tìm kiếm toàn văn; có thể ghép vector search | Tìm kiếm và phân tích truy vấn mạnh hơn FTS5 ở nhu cầu phù hợp | **Không triển khai**; analyzer tiếng Việt cần thiết kế/đánh giá riêng |
| Big Data (HDFS/S3 + Parquet/Delta/Iceberg) | Lưu trữ phân tán dạng cột cho dữ liệu lớn và xử lý batch | Nén, partition, scale-out và xử lý theo lô | **Không triển khai**; hiện tại chỉ dùng Parquet cục bộ, chưa có hệ thống phân tán |
| fastText | Embedding subword huấn luyện từ corpus nội miền | Có thể tạo vector từ và giảm vấn đề từ ngoài từ vựng | **Không triển khai**; corpus synthetic/nhỏ không đủ để kết luận chất lượng |
| PhoBERT | Transformer tiền huấn luyện cho tiếng Việt; thường cần đầu vào đã tách từ theo định dạng mô hình | Biểu diễn ngữ cảnh tiếng Việt | **Không triển khai**; chi phí tài nguyên và đánh giá nhãn tay chưa được thực hiện |

Lộ trình hợp lý là: (1) kiểm tra thủ công F06 và tỷ lệ token một ký tự; (2) xây tập nhãn tay được phép sử dụng và báo macro-F1 trên nhãn thật tách biệt nhãn proxy; (3) xác minh collector bằng mẫu phản hồi live đã ẩn danh, nếu có quyền; (4) chỉ sau khi workload yêu cầu mới benchmark một backend tìm kiếm/NoSQL hoặc kiến trúc Big Data thực sự.


## Trạng thái triển khai

- Import/Synthetic: chạy offline; Playwright/GraphQL chưa được xác minh bằng mẫu phản hồi Facebook thật.
- Preprocess S0–S11: đã có mã, test hồi quy tiếng Việt và metric `token_quality` (tỷ lệ token một ký tự; cảnh báo khi vượt 10%).
- Represent/label/store: BoW/TF-IDF, nhãn proxy, SQLite/FTS5 và Parquet có mã; E5 là tùy chọn và bị bỏ qua trong demo offline.
- F01/F03/F06/F07/F09/F10/F11/F13/F14/F15 được sinh bởi `fbpipe demo`. Cần duyệt hình vừa sinh và top 15 F06; hình được tạo trên runner CI không tự cập nhật các PNG đã commit trong repository.

## Nhận định tổng kết

<!-- TRUNG VIẾT: dựa trên số liệu thật được phép sử dụng; không đưa dữ liệu synthetic/benchmark clone thành kết quả từ Facebook. -->

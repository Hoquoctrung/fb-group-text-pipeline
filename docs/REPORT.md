# Báo cáo — FB Group Text Pipeline (phạm vi rút gọn Phase 0–6)

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

## Trạng thái triển khai

- **Import/Synthetic:** có đường nhập CSV/JSONL và sinh dữ liệu synthetic offline. `PlaywrightCollector` có mã tối thiểu nhưng crawl live và schema GraphQL thật chưa được xác minh.
- **Preprocess S0–S11:** được triển khai và có unit tests; số liệu phải đọc từ metrics của lượt chạy hiện tại, không lấy số liệu synthetic làm bằng chứng về nhóm thật.
- **Represent/Store:** BoW, TF-IDF, E5 tùy chọn, SQLite+FTS5 và Parquet có code. Demo chuẩn dùng `--skip-e5` để không tải model. Đánh giá nhãn chỉ được coi là ground truth khi có nhãn người gán và kiểm tra.
- **Analyze/Viz/Report:** CLI tạo 10 hình tĩnh F01/F03/F06/F07/F09/F10/F11/F13/F14/F15 và sinh `docs/REPORT_generated.md`; dashboard Streamlit không triển khai.
- **CI:** kiểm tra Ruff, format, bộ unit tests offline và smoke test `fbpipe demo` sau khi xóa `data/`. Lấy trạng thái cuối cùng từ tab Actions, không suy ra CI xanh chỉ từ test cục bộ.

## Nguồn dữ liệu & giới hạn

- Quy trình demo mặc định sinh **200 bản ghi synthetic** bằng seed cố định. Đây là dữ liệu mô phỏng để kiểm tra pipeline, không phải bài đăng Facebook thật. Demo preprocess thư mục `data/bronze/demo/` riêng, tránh trộn các file Bronze khác vào mẫu demo.
- Khi có dữ liệu import được phép, lấy **N bài import** từ `source_counts` trong `data/metrics/analyze.json` sau khi chạy lại pipeline; ghi nguồn và phạm vi thu thập thực tế. Không lấy `N` từ tên file hoặc số dòng benchmark.
- **Crawl live chưa xác minh**: chưa có bằng chứng về tỷ lệ parse thành công trên response GraphQL thật đã ẩn danh. Fixture tự dựng không chứng minh crawler hoạt động trên Facebook.
- **Nhãn:** hiện chưa có bộ nhãn tay được cung cấp để khẳng định hiệu năng phân loại. Khi đánh giá dùng nhãn yếu theo luật, metrics phải ghi `proxy_labels=true`; không gọi đây là ground truth.
- **Benchmark:** mốc 1.000 bản ghi là bootstrap/clone có nhiễu từ Silver với ID mới, không phải 1.000 bài độc lập. Đây chỉ là phép đo kỹ thuật trên dữ liệu mô phỏng.
- Chỉ công bố các hình/bảng sau khi rà soát để bảo đảm không lộ PII; không đưa dữ liệu thật, cookies, token, `.env` hoặc `.auth/` lên GitHub.

## Hạn chế & hướng phát triển

Các công nghệ trong bảng dưới là so sánh lý thuyết để định hướng, không phải kết quả benchmark thực nghiệm của triển khai hiện tại.

| Công nghệ | Vai trò / điểm mạnh về lý thuyết | Hạn chế / chi phí cần cân nhắc | Trạng thái dự án |
|---|---|---|---|
| SQLite + FTS5 | Database quan hệ cục bộ, giao dịch và full-text search trong một file | Một node; ghi đồng thời và quy mô lớn có giới hạn | **Đã triển khai** |
| Parquet | Định dạng cột, nén tốt, quét phân tích theo cột | Không tự cung cấp full-text index hoặc giao dịch kiểu DB | **Đã triển khai** |
| MongoDB | Tài liệu JSON linh hoạt, phù hợp dữ liệu lồng nhau | Cần vận hành service, index và quản trị quyền/backup | **Chỉ mô tả lý thuyết — không triển khai** |
| Elasticsearch | BM25, analyzers, highlight; có thể hỗ trợ tìm kiếm vector tùy cấu hình | Chi phí RAM/vận hành; analyzer tiếng Việt cần đánh giá riêng | **Chỉ mô tả lý thuyết — không triển khai** |
| Big Data (HDFS/S3, Delta/Iceberg, DuckDB) | Lưu trữ phân tán hoặc truy vấn cột ở quy mô lớn | Phức tạp hơn và có chi phí vận hành; DuckDB cũng chưa được tích hợp trong bản rút gọn | **Chỉ mô tả lý thuyết — không triển khai** |
| fastText | Embedding từ hiệu quả, biểu diễn subword hữu ích với từ hiếm/biến thể | Cần huấn luyện/chọn corpus và đánh giá theo miền dữ liệu | **Chỉ mô tả lý thuyết — không triển khai** |
| PhoBERT | Transformer tiền huấn luyện tiếng Việt, có ngữ cảnh câu | Nặng hơn BoW/TF-IDF; cần tokenizer, tài nguyên và đánh giá nhãn đáng tin cậy | **Chỉ mô tả lý thuyết — không triển khai** |

**Hướng phát triển có điều kiện:** (1) xin phép và xác minh mẫu live đã ẩn danh trước khi đánh giá parser; (2) gán nhãn tay và đo agreement trước khi công bố F1; (3) bổ sung các ablation và hình còn thiếu nếu rubric yêu cầu; (4) chỉ triển khai MongoDB/Elasticsearch/Big Data hoặc mô hình embedding khác khi có câu hỏi đo lường và ngân sách phù hợp. Không mô tả các mục này như tính năng hiện có.

## Nhận định tổng kết

<!-- TRUNG VIẾT: dựa trên số liệu thật được phép sử dụng; không đưa dữ liệu synthetic/benchmark clone thành kết quả từ Facebook. -->

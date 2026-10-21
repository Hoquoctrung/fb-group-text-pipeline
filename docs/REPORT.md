Báo cáo đồ án: Pipeline xử lý văn bản từ nhóm Facebook

Sinh viên: Hồ Quốc Trung
MSSV: 24521878
Môn: CS232
Mã nguồn: https://github.com/Hoquoctrung/fb-group-text-pipeline (tag v1.0)
Báo cáo số liệu tự động: REPORT_generated.md

Lưu ý trung thực về dữ liệu: Toàn bộ kết quả trong báo cáo này được đo trên 200 bài viết tổng hợp (synthetic) do SyntheticCollector sinh ra. Chưa thu thập được dữ liệu thật từ nhóm Facebook (xem §7 và §9). Các kết quả vì vậy chứng minh pipeline chạy đúng, không phản ánh nội dung hay hành vi của nhóm thật.

Tóm tắt

Đồ án xây dựng pipeline xử lý văn bản đầu-cuối gồm 5 giai đoạn: thu thập, tiền xử lý, biểu diễn, lưu trữ, phân tích và trực quan hóa. Pipeline chạy được bằng một chuỗi lệnh CLI (fbpipe), mỗi giai đoạn ghi số liệu vào data/metrics/\*.json và báo cáo tự động được sinh từ các file này. Do giới hạn thời gian (48 giờ) và rủi ro truy cập Facebook, phạm vi được rút gọn có chủ đích (xem §9).

Giai đoạn Kết quả đạt được
Thu thập ImportCollector, SyntheticCollector, PlaywrightCollector (chưa xác minh live)
Tiền xử lý Bước S0–S11, ablation 3 cấu hình; 200 bài → 53 bài giữ lại sau lọc trùng/spam/ngắn
Biểu diễn BoW, TF-IDF, E5 (tùy chọn); đánh giá bằng nhãn proxy
Lưu trữ SQLite + FTS5, Parquet; benchmark 1.000 bản ghi nhân bản
Trực quan hóa Các hình F01, F03, F06, F07, F09, F10, F11, F13, F14, F15 (xem §6)

1. Kiến trúc và quy trình
   CollectImport · Synthetic ·Playwright
   BronzeJSONL
   PreprocessS0–S11
   SilverParquet
   RepresentBoW · TF-IDF · E5
   Gold.npz / .npy
   StoreSQLite · Parquet
   Analyze & Viz
   Figures ·REPORT_generated.md
   Giai đoạn Đầu vào Đầu ra Vai trò Công cụ Số đo
   Collect Nguồn (file / synthetic / web) data/bronze/_.jsonl Đưa dữ liệu về schema RawPost thống nhất, ẩn danh tác giả Pydantic, Playwright số bài, số dòng lỗi
   Preprocess Bronze data/silver/documents.parquet Làm sạch, chuẩn hóa, tách từ, lọc chất lượng underthesea, NLTK, datasketch funnel, OOV, thời gian từng bước
   Represent Silver data/gold/ Chuyển văn bản thành vector scikit-learn, sentence-transformers chiều, độ thưa, macro-F1
   Store Silver data/fbpipe.db, data/store/_.parquet Truy vấn và lưu trữ lâu dài SQLite FTS5, pyarrow thời gian truy vấn
   Analyze/Viz Silver, Gold, metrics docs/figures/ Quan sát và trình bày kết quả matplotlib, scikit-learn —

Thiết kế theo mô hình medallion (Bronze → Silver → Gold): mỗi tầng tái tạo được từ tầng trước, mỗi giai đoạn idempotent và ghi metrics riêng. Mẫu Adapter cho Collector giúp các giai đoạn sau không phụ thuộc nguồn dữ liệu, nên khi Facebook chặn truy cập thì pipeline vẫn chạy trên dữ liệu nhập tay hoặc synthetic.

2. Thu thập dữ liệu
   Bảng 1. So sánh 5 kỹ thuật thu thập
   Kỹ thuật Định nghĩa ngắn Dùng khi Ưu điểm Nhược điểm Hiện thực trong đồ án
   File import Đọc dataset CSV/JSONL có sẵn Có dữ liệu được phép sử dụng Ổn định, nhanh, tái lập Phụ thuộc nguồn dữ liệu ImportCollector (đã chạy, kiểm thử)
   Web scraping Trích nội dung từ HTML/DOM đã render Cần dữ liệu hiển thị trên trang Linh hoạt, không cần API Dễ vỡ khi UI đổi Không triển khai DOM parser
   Crawling Duyệt nhiều trang/feed với checkpoint và giới hạn tốc độ Cần nhiều bản ghi Phủ rộng Phụ thuộc schema và trạng thái truy cập PlaywrightCollector tối thiểu, chưa xác minh live
   API Gọi endpoint chính thức, dữ liệu có cấu trúc Nền tảng cung cấp quyền truy cập Sạch, ổn định hơn Quyền bị giới hạn hoặc gỡ Chỉ mô tả
   Streaming Nhận và xử lý dữ liệu liên tục Cần gần thời gian thực Độ trễ thấp Cần hạ tầng, xử lý sự kiện trễ Chỉ mô tả

Về Facebook: Meta đã ngừng hỗ trợ Groups API trong Graph API (từ v19, 01/2024), các thư viện scraper không chính thức không còn ổn định. Vì vậy hướng Playwright dùng phiên đăng nhập do chính người dùng tạo, chỉ nghe phản hồi trang tự tải, tốc độ thấp, và dừng ngay (mã thoát 3) khi gặp login wall/captcha/hạn chế. Không có mã nào nhằm né chặn. Chi tiết ở docs/ETHICS.md.

Trạng thái: parser GraphQL được kiểm thử bằng fixture tự dựng; chưa có mẫu phản hồi thật từ fbpipe probe nên key path của Facebook chưa được xác minh (TODO(real-sample)).

3. Tiền xử lý

Pipeline gồm các Transform độc lập (S0–S11): nhận diện ngôn ngữ, chuẩn hóa Unicode NFC, xóa nhiễu giao diện, che PII (URL/email/SĐT), xử lý emoji, rút gọn ký tự kéo dài, chuẩn hóa teencode, chữ thường, tách từ (underthesea), stopwords, stem/lemma, lọc chất lượng.

Lập trường về stemming/lemmatization: tiếng Việt là ngôn ngữ đơn lập, không biến hình theo thì/số, nên stemming theo nghĩa tiếng Anh không áp dụng. Phần tương đương là chuẩn hóa dấu, teencode, tách từ và chữ thường. Stem/lemma chỉ áp dụng cho token tiếng Anh hợp lệ trong văn bản code-mixed; token tiếng Việt được giữ nguyên (identity).

Funnel làm sạch (F15):

Bước Số bài
Đầu vào (raw) 200
Sau loại trùng (MinHash, ngưỡng 0,85) 53
Sau lọc spam 53
Sau lọc bài quá ngắn 53
Giữ lại (keep) 53

147/200 bài bị đánh dấu trùng. Đây là đặc điểm của bộ synthetic (cố ý sinh repost), không nên đọc như tỷ lệ trùng của một nhóm thật.

Ablation (3 cấu hình): A0_strip_only, A1_clean_and_tokenize, A2_full_s0_s11. Kết quả (kích thước từ vựng, độ dài token) xem data/metrics/preprocess.json và REPORT_generated.md. <!-- ĐIỀN: dán 3 dòng số từ preprocess.json -->

Giới hạn đo lường: corpus tham chiếu NLTK English không có trong lần chạy, nên OOV tiếng Anh ghi null (không phải 0) và nhánh stem/lemma tiếng Anh bị tắt.

4. Biểu diễn văn bản
   Biểu diễn Cách làm Ưu Nhược
   BoW CountVectorizer, n-gram (1,2) trên tokens_nostop Đơn giản, giải thích được Thưa, bỏ qua ngữ nghĩa và thứ tự
   TF-IDF TfidfVectorizer(sublinear_tf=True), tf-idf(t,d) = tf(t,d) × idf(t) Hạ trọng số từ phổ biến Vẫn không biết đồng nghĩa
   E5 multilingual-e5-small, input text_clean, chuẩn hóa L2 Bắt ngữ nghĩa, chịu code-mixed Cần model, chậm hơn trên CPU

Trên 53–200 tài liệu synthetic, BoW và TF-IDF cùng có 148 chiều (ma trận thưa, lưu .npz). E5 là tùy chọn: thiếu thư viện hoặc không tải được model thì pipeline vẫn chạy với hai biểu diễn thưa, và metrics ghi trạng thái E5 bị bỏ qua.

Đánh giá: chưa có nhãn tay nên label-eval dùng nhãn luật (proxy), mọi bảng/hình gắn cờ proxy_labels=true. Điểm macro-F1 theo nhãn proxy chỉ mang tính chẩn đoán vì nhãn do luật sinh nên mô hình học lại chính luật đó; không phải macro-F1 trên ground truth. <!-- ĐIỀN: macro-F1 BoW / TF-IDF / E5 từ label_eval.json -->

Chọn biểu diễn: dữ liệu ít và cần giải thích → TF-IDF; cần tìm theo nghĩa hoặc code-mixed → E5. Vì dữ liệu hiện tại là synthetic, khuyến nghị này chưa được kiểm chứng bằng số đo trên dữ liệu thật.

5. Lưu trữ
   Bảng 4. So sánh lưu trữ
   Backend Đặc trưng Trạng thái
   SQLite + FTS5 Upsert theo doc_id, lọc ngày, đếm theo tháng, tìm toàn văn bằng chỉ mục đảo Đã triển khai, benchmark
   Parquet Lưu cột, nén, quét bằng pandas/pyarrow, không có chỉ mục full-text Đã triển khai, benchmark
   PostgreSQL SQL đầy đủ, tsvector, đa người dùng Chỉ mô tả, không triển khai
   MongoDB Document lồng (post chứa comments), schema linh hoạt Chỉ mô tả, không triển khai
   Elasticsearch Full-text, kNN, highlight; cần analyzer tiếng Việt Chỉ mô tả, không triển khai
   DuckDB / HDFS / S3 + Iceberg Truy vấn SQL trực tiếp trên Parquet; lưu trữ phân tán Chỉ mô tả, không triển khai

Benchmark (F14): 1.000 bản ghi nhân bản từ Silver (ID mới), 20 lần lặp, median, lần chạy warm.

Tác vụ SQLite + FTS5 Parquet
Ghi bulk ≈ 0,18 s ≈ 0,01 s
Tìm từ khóa ≈ 0,001 s ≈ 0,008 s
Lọc theo ngày ≈ 0,017 s ≈ 0,018 s
Đếm theo tháng ≈ 0 ≈ 0,006 s

Nhận xét: SQLite mạnh ở truy vấn điểm và tìm kiếm nhờ chỉ mục (FTS5, index ngày); Parquet mạnh ở ghi hàng loạt và phân tích theo cột. Vì vậy dự án dùng SQLite để tra cứu, Parquet để lưu trữ phân tích. Giới hạn: chỉ 1.000 bản ghi nhân bản, chênh lệch ở mức mili-giây nên chỉ mang tính gợi ý; ghi bulk của SQLite còn gồm dựng chỉ mục FTS5 nên phép so sánh không hoàn toàn công bằng; "Parquet scan" là quét trực tiếp, chưa có engine truy vấn. Ở quy mô lớn hơn (≥ hàng triệu bản ghi hoặc nhiều người ghi đồng thời) mới cần Postgres/Elasticsearch hoặc kho Big Data thật.

6. Trực quan hóa

Các hình sinh bằng fbpipe viz, lưu trong docs/figures/ (đã duyệt tay, không lộ tên/SĐT):

Hình Nội dung Ghi chú đọc kết quả
F01 Số bài theo ngày Phân bố gần đều là đặc điểm của synthetic, không phải xu hướng thật
F03 Phân bố độ dài bài (token)
F06 Top term: TF vs TF-IDF <!-- KIỂM TRA: nếu còn token vỡ ("th", "ng", "ười") thì ghi rõ lỗi tách từ -->
F07 Word cloud Lọc PII/tên riêng bằng heuristic, không thay thế NER
F09 Chọn k cho LDA Ghi đúng đại lượng được vẽ (c_v hay thay thế)
F10 Chủ đề LDA sklearn LDA, số vòng lặp nhỏ
F11 Bản đồ embedding 2D Ghi rõ UMAP/E5 hay PCA/TF-IDF thay thế
F13 So sánh biểu diễn Dùng nhãn proxy (proxy_labels=true)
F14 Benchmark lưu trữ Bản ghi nhân bản
F15 Funnel làm sạch 200 → 53 7. Thách thức thực tế

Bảng đầy đủ (15 mục) ở docs/CHALLENGES.md. Các thách thức nổi bật gặp trong dự án:

Thách thức Biểu hiện trong dự án Giải pháp Rủi ro còn lại
Truy cập Facebook Groups API bị gỡ; schema nội bộ không công bố; chưa có mẫu probe thật Adapter pattern; Import/Synthetic làm đường dự phòng; dừng khi bị chặn Chưa crawl được dữ liệu thật
Pháp lý/đạo đức ToS hạn chế thu thập tự động; dữ liệu cá nhân Băm tác giả (HMAC), che PII, không commit dữ liệu thật, ETHICS.md Cần xác nhận quyền trước khi crawl
Nhiễu và trùng lặp Repost, teencode, emoji MinHash dedup, chuẩn hóa teencode; funnel 200 → 53 Danh sách teencode còn nhỏ
Tách từ tiếng Việt Lỗi tách từ lan sang mọi biểu diễn phía sau Kiểm thử bảng input/output, theo dõi tỷ lệ token độ dài 1 <!-- CẬP NHẬT: đã sửa hay chưa -->
Không có ground truth Chưa có nhãn tay Nhãn proxy gắn cờ rõ ràng; label-sample sẵn sàng cho nhãn tay Điểm macro-F1 chưa phản ánh chất lượng thật
Đánh giá và quy mô Benchmark chỉ 1k bản ghi nhân bản Nêu rõ giới hạn Chưa biết nút thắt ở 100k+
Tái lập Seed, secret, phiên bản thư viện seed=42, .env không commit, CI chạy test offline Chưa khóa phiên bản (lockfile) 8. Nhận định

<!-- TRUNG: đọc lại, sửa theo đúng những gì bạn quan sát. Dưới đây là bản nháp trung thực, không thay thế nhận xét của bạn. -->

Dữ liệu. Pipeline chạy trên 200 bài synthetic, nên các hình về thời gian (F01), trùng lặp (F15) và chủ đề (F10) chủ yếu phản ánh cách sinh dữ liệu chứ không phải một cộng đồng thật. Ví dụ F01 gần như phẳng vì synthetic sinh đều theo ngày.
Tiền xử lý. Funnel 200 → 53 cho thấy bước loại trùng ảnh hưởng nhiều nhất; quan sát này cho thấy bước dedup hoạt động, còn tỷ lệ thật của nhóm thì chưa biết.
Biểu diễn. BoW/TF-IDF cho vector thưa, giải thích được (148 chiều ở quy mô nhỏ). Chưa có nhãn tay nên chưa thể kết luận E5 hay TF-IDF tốt hơn; đây là điểm đồ án chưa trả lời được.
Lưu trữ. SQLite thắng ở tìm kiếm nhờ FTS5, Parquet thắng ở ghi hàng loạt. Với quy mô hiện tại, chênh lệch rất nhỏ và không đủ để kết luận cho quy mô lớn.
Bài học chính. Thiết kế adapter giúp bài vẫn hoàn chỉnh khi nguồn thật bị chặn; một lỗi tiền xử lý (nếu có) có thể làm sai mọi bước sau, nên cần kiểm thử xuyên suốt pipeline chứ không chỉ từng bước riêng lẻ. 9. Hạn chế và hướng phát triển

Hạn chế đã biết:

Chưa thu thập dữ liệu thật; auth, probe, crawl chưa được chạy end-to-end, parser chưa khớp schema thật.
Nhãn đánh giá là proxy; chưa có macro-F1 trên nhãn tay.
Phạm vi rút gọn (§0b của SPEC): không triển khai MongoDB, Elasticsearch, PostgreSQL, DuckDB, Streamlit, fastText tự huấn luyện, PhoBERT, NMF/BERTopic, dashboard; chỉ mô tả lý thuyết.
Ablation 3 cấu hình thay vì 8; benchmark chỉ ở 1.000 bản ghi; có 1 notebook demo hoặc chưa có (ghi đúng thực tế).
F07 dùng heuristic lọc tên riêng; F10 dùng LDA cấu hình nhẹ.

Hướng phát triển: xin phép và thu thập dữ liệu thật (hoặc dữ liệu do giảng viên cấp) qua ImportCollector; gán nhãn tay 150–200 bài và tính Cohen's κ; benchmark ở 10k–100k; thêm engine truy vấn trên Parquet (DuckDB) và Elasticsearch với analyzer tiếng Việt; so sánh underthesea với pyvi; mở rộng ablation.

Tài liệu tham khảo
Meta (23/01/2024), Introducing Facebook Graph API v19.0 and Marketing API v19.0.
TechCrunch (05/02/2024), Meta cuts off third-party access to Facebook Groups.
intfloat/multilingual-e5-small (Hugging Face); underthesea; datasketch; scikit-learn; NLTK; SQLite FTS5; Apache Parquet.
Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân (kiểm tra văn bản hiện hành trước khi trích).

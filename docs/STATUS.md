# Trạng thái dự án — FB Group Text Pipeline

**Cập nhật:** 2026-10-22  
**Phạm vi:** docs/SPEC.md §0b, các Phase 0–6 trong phạm vi rút gọn.  
**Nhánh đang làm:** fix/vietnamese-tokenization-quality  
**Pull request:** [#1 — Fix Vietnamese tokenization and add offline demo](https://github.com/Hoquoctrung/fb-group-text-pipeline/pull/1)  
**Trạng thái PR:** đang mở, chưa merge vào main.

> Trạng thái bên dưới dựa trên code hiện có và log GitHub Actions. Bản demo dùng dữ liệu synthetic; chưa có bằng chứng crawl Facebook live thành công. Không commit dữ liệu sinh ra, .env, .auth/ hoặc thông tin cá nhân.

## 1. Snapshot kiểm chứng mới nhất

CI của PR #1 chạy trên checkout sạch, xóa data/ trước test và demo.

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Ruff lint | ✅ Pass | ruff check . → All checks passed |
| Ruff format | ✅ Pass | ruff format --check src tests → 44 files already formatted |
| Test offline | ✅ Pass | 81 passed in 7.15s |
| Demo end-to-end | ✅ Pass | make demo thành công từ data/ trống |
| Thời gian demo | ✅ Đạt | 20,43 giây theo timer bên trong demo; 21,90 giây thời gian thực của lệnh shell |
| Preprocess | ✅ Pass | 200 synthetic posts, 0 invalid records |
| Represent | ✅ Pass | BoW 105 chiều, TF-IDF 105 chiều; E5 skipped/unavailable trong demo offline |
| Label evaluation | ✅ Pass | 200 nhãn proxy; proxy_labels=true |
| Store | ✅ Pass | 200 rows vào SQLite/FTS5 và 200 rows vào Parquet |
| Analyze | ✅ Pass | 200 documents; source counts: synthetic=200, import=0, playwright=0, unknown=0 |
| Viz | ✅ Pass | Sinh 10 hình: F01, F03, F06, F07, F09, F10, F11, F13, F14, F15 |
| Report | ✅ Pass | docs/REPORT_generated.md; 6 metrics files đọc được, 0 lỗi |

**Giới hạn của bằng chứng:** đây là kết quả CI trên dữ liệu synthetic. Kích thước vector trong demo (105 chiều) thuộc lần chạy demo mới; lần chạy Phase 3–4 trước đó đã ghi nhận 148 chiều với bộ dữ liệu/đầu vào của lần chạy đó. Không dùng các số này để kết luận về bài đăng Facebook thật.

## 2. Lỗi token tiếng Việt — đã sửa và có regression tests

**Nguyên nhân gốc:** nhánh ASCII [A-Za-z]+ trong _TOKEN_RE được xét trước nhánh Unicode, nên có thể tiêu thụ tiền tố ASCII của một từ tiếng Việt và làm phần có dấu còn lại thành token riêng.

**Thay đổi:**
- Sửa regex trong src/fbpipe/preprocess/steps.py theo hướng Unicode-aware, không ưu tiên nhánh ASCII-only trước chữ tiếng Việt.
- Thêm scripts/trace_preprocess_s1_s7.py để chạy độc lập từng transform S1–S7 trên chuỗi "chia sẻ thông tin về mọi người" và in kết quả sau mỗi transform.
- Thêm test bảng cho "Chia sẻ thông tin về mọi người", "Việt Nam đẹp quá 😍 !!!" và "liên hệ 0901234567 hoặc a@b.com".
- Giữ kiểm tra text_clean nghiêm ngặt, còn tokens chấp nhận các cách gộp từ hợp lệ của Underthesea như việt_nam / việt, nam và liên_hệ / liên, hệ.
- Thêm token_quality vào metrics preprocess: tổng token, số token dài một ký tự, tỷ lệ và cảnh báo khi tỷ lệ **thực tế chưa làm tròn** vượt 10%.

**Bằng chứng F06 mới (200 bài synthetic):** các token người, thông_tin và chia_sẻ xuất hiện nguyên vẹn. Top 15 TF và TF-IDF đã được in ra log demo. Chưa tuyên bố đã kiểm tra trên dữ liệu crawl thật.

### Top TF của F06 trong lần chạy demo

| Hạng | Token | Số lần |
|---:|---|---:|
| 1 | về | 133 |
| 2 | mọi | 86 |
| 3 | người | 86 |
| 4 | chia_sẻ | 83 |
| 5 | mình | 74 |
| 6 | thông_tin | 55 |
| 7 | học_tập | 40 |
| 8 | lập_trình | 40 |
| 9 | sự_kiện | 40 |
| 10 | việc_làm | 40 |
| 11 | anh_chị | 32 |
| 12 | biết | 32 |
| 13 | không | 32 |
| 14 | nào | 32 |
| 15 | hỏi | 30 |

## 3. fbpipe demo và make demo

Đã triển khai:
- fbpipe demo chạy lần lượt synth --n 200 → preprocess --force → represent --skip-e5 → label-eval → store → analyze → viz → report.
- make demo gọi fbpipe demo.
- Demo ghi dữ liệu vào data/demo/ và chỉ reset thư mục demo; không xóa file import hay nhãn tay ở các đường dẫn dữ liệu khác.
- In thời gian từng stage, tổng thời gian, top 15 TF và top 15 TF-IDF của F06; fail nếu vượt giới hạn 90 giây.
- GitHub Actions có smoke test riêng: xóa data/ trong runner sạch rồi chạy timeout 90s make demo.

## 4. Trạng thái theo phase

| Phase | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| 0 — Scaffold | ✅ Hoàn thành trong phạm vi | Package, config, schema, privacy, logging, CLI, metrics, .gitignore, pre-commit và CI |
| 1 — Collect | 🟡 Adapter và test đã có | Import/Synthetic chạy offline; Playwright auth/probe/crawl/resume với Facebook live **chưa xác minh** |
| 2 — Preprocess | ✅ Code, test và demo pass | S0–S11, ablation 3 cấu hình, Bronze → Silver Parquet, provenance và cảnh báo chất lượng token |
| 3 — Represent/Label | ✅ Phạm vi rút gọn | BoW/TF-IDF; E5 tùy chọn; nhãn proxy được gắn cờ. Chưa có kết quả macro-F1 trên nhãn tay |
| 4 — Store/Benchmark | ✅ Phạm vi rút gọn | SQLite + FTS5, Parquet; benchmark 1k clone, không phải 1.000 bài độc lập |
| 5 — Analyze | ✅ Demo pass | Metrics tổng hợp, số liệu nguồn và token top-term |
| 6 — Viz/Report | ✅ Demo pass | 10 hình và báo cáo metrics sinh thành công trên runner; artifact runtime không tự đồng nghĩa PNG/báo cáo đã được commit |

## 5. Tài liệu được cập nhật trong nhánh PR

- README.md: badge CI, mô tả rút gọn, Mermaid kiến trúc, 4 hình đầu ra, Quickstart, bảng 7 mục tiêu theo SPEC §1, cảnh báo đạo đức, giới hạn và English summary.
- docs/REPORT.md: giữ nguyên nội dung phần **Nhận định** của bản báo cáo mới trên main và thêm nội dung về tokenization, nguồn dữ liệu, nhãn proxy, crawl live chưa xác minh, benchmark clone cùng bảng so sánh lý thuyết. Không viết thay phần nhận định của Trung.
- docs/STATUS.md: tài liệu trạng thái hiện hành này.
- .github/workflows/ci.yml: test offline và end-to-end demo giới hạn 90 giây.

Các file sinh ra khi chạy gồm data/demo/, docs/figures/ và docs/REPORT_generated.md. Hãy kiểm tra .gitignore và git status trước khi commit; không tự động commit dữ liệu hoặc metrics runtime.

## 6. Giới hạn còn lại / việc tiếp theo

1. Chờ merge PR #1 vào main; tại snapshot này PR vẫn đang mở.
2. Nếu tiếp tục làm trên máy cá nhân, chạy make demo và duyệt docs/figures/F06_top_terms_tf_tfidf.png sau khi cài dependency; không cần dùng dữ liệu Facebook thật để smoke test.
3. Nếu có dữ liệu import được phép, kiểm tra provenance và duyệt thủ công F06 cùng tỷ lệ token một ký tự trước khi diễn giải kết quả.
4. Chỉ chạy Facebook auth/probe/crawl sau khi xác nhận quyền truy cập; dừng ngay khi xuất hiện login wall, checkpoint, CAPTCHA hoặc thông báo hạn chế. Chưa có mẫu response thật đã ẩn danh để xác minh parser.
5. Thu thập và kiểm tra nhãn tay nếu cần đánh giá mô hình thực sự; tới lúc đó, proxy_labels=true không phải ground truth.
6. MongoDB, Elasticsearch, PostgreSQL/DuckDB, HDFS/S3/Big Data, fastText tự huấn luyện, PhoBERT, Streamlit, NMF/BERTopic, capture–recapture và streaming/API demos tiếp tục nằm ngoài phạm vi triển khai theo SPEC §0b; chỉ mô tả lý thuyết nơi phù hợp.
7. Chưa có notebook demo trong danh sách file đã kiểm tra. Chỉ tạo một notebook nếu còn thời gian; không dựng lại bảy notebook đã loại khỏi phạm vi.

## 7. Lệnh kiểm chứng

Tại root repository, với .venv đã kích hoạt:

~~~bash
ruff check .
ruff format --check src tests
pytest -m "not integration and not slow" -q
make demo

git diff --check
git status --short
~~~

Trước commit/push, xác nhận không stage .env, .auth/, dữ liệu thật, data/ hoặc artifact metrics nhạy cảm. PR #1 đã có CI xanh cho commit c3e39bfcdd246391c675f20de19eac8eebb31c32; thay đổi STATUS.md này sẽ tạo commit mới và kích hoạt CI mới.

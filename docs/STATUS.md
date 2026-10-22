# Trạng thái dự án — FB Group Text Pipeline

**Cập nhật:** 2026-10-22  
**Phạm vi:** docs/SPEC.md §0b và Phase 0–6 trong phạm vi rút gọn.  
**Trạng thái mã nguồn:** PR #1 đã merge vào main. PR #2 cập nhật trạng thái chạy demo tại máy phát triển.

> Demo tạo dữ liệu synthetic, không crawl Facebook. Không mô tả kết quả synthetic, nhãn proxy hoặc benchmark clone thành kết quả từ nhóm Facebook thật.

## 1. Snapshot kiểm chứng mới nhất

### CI sau khi merge PR #1

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Ruff lint | Pass | ruff check . → All checks passed |
| Ruff format | Pass | 44 files already formatted |
| Test offline | Pass | 81 passed in 7.15s |
| Demo từ data trống | Pass | make demo hoàn tất dưới 90 giây |
| Thời gian demo trên GitHub Actions | 20,43 giây | Timer bên trong demo; thời gian shell 21,90 giây |
| Preprocess | Pass | 200 synthetic posts, 0 invalid |
| Represent | Pass | BoW 105 chiều, TF-IDF 105 chiều, E5 bị bỏ qua trong demo offline |
| Label evaluation | Pass | 200 labels; proxy_labels=true |
| Store | Pass | 200 rows SQLite/FTS5, 200 rows Parquet |
| Analyze | Pass | synthetic=200, import=0, playwright=0, unknown=0 |
| Viz | Pass | Sinh 10 hình |
| Report | Pass | 6 metrics files, 0 lỗi, 10 hình được nhận diện |

### Chạy tại máy phát triển sau khi cập nhật main

Người phát triển đã chạy thành công git pull origin main rồi make demo trên MacBook vào ngày 22/10/2026.

| Bước | Kết quả Terminal |
|---|---|
| Sinh dữ liệu | 200 synthetic posts |
| Preprocess | 200 posts; 0 invalid records |
| Represent | BoW 105 chiều; TF-IDF 105 chiều; E5 skipped/unavailable |
| Label evaluation | 200 labels; proxy_labels=true |
| Store | 200 rows SQLite/FTS5 và 200 rows Parquet |
| Analyze | 200 documents; synthetic=200 và các nguồn import/playwright/unknown đều bằng 0 |
| Viz | Sinh 10 hình: F01, F03, F06, F07, F09, F10, F11, F13, F14, F15 |
| Report | docs/REPORT_generated.md; 6 metrics files, 0 lỗi, 10 hình |
| Tổng thời gian | 26,21 giây, đạt yêu cầu dưới 90 giây |

Từng bước trong lần chạy Mac: synth 1,81s; preprocess 7,87s; represent 1,77s; label-eval 1,81s; store 1,71s; analyze 1,76s; viz 7,83s; report 1,64s. Đây là một lần chạy cụ thể, không phải benchmark tổng quát.

### Cảnh báo trong log demo

- RuntimeWarning của label-eval xác nhận không có nhãn tay và đang dùng nhãn proxy; đây là hành vi dự kiến. Các điểm macro-F1 (BoW 1.0, TF-IDF 0.89093) chỉ là chẩn đoán theo nhãn proxy, không phải kết quả trên ground truth.
- Hai thông báo matplotlib.category là mức INFO, không làm demo thất bại.
- Demo được thiết kế để reset data/demo; không xóa các file import/nhãn ở đường dẫn dữ liệu khác. Hình trong docs/figures và docs/REPORT_generated.md được sinh lại để phản ánh lượt demo vừa chạy.

**Lưu ý về số chiều:** demo mới tạo 105 chiều cho BoW/TF-IDF. Lần chạy Phase 3–4 trước đây ghi 148 chiều với đầu vào của lần chạy đó. Không nên so sánh các số này như một thay đổi chất lượng mô hình khi dữ liệu, nguồn và phạm vi đầu vào khác nhau.

## 2. Lỗi token tiếng Việt — đã sửa

**Nguyên nhân gốc:** nhánh ASCII-only [A-Za-z]+ trong regex tokenizer được đặt trước nhánh Unicode, có thể làm vỡ từ tiếng Việt tại tiền tố ASCII.

Đã cập nhật:
- Regex Unicode-aware trong src/fbpipe/preprocess/steps.py.
- Script scripts/trace_preprocess_s1_s7.py chạy riêng từng transform S1–S7 với chuỗi “chia sẻ thông tin về mọi người”.
- Test bảng cho “Chia sẻ thông tin về mọi người”, “Việt Nam đẹp quá 😍 !!!” và “liên hệ 0901234567 hoặc a@b.com”.
- Điều kiện test nghiêm ngặt cho text_clean; tokens chấp nhận cả cụm từ ghép hợp lệ từ Underthesea, ví dụ việt_nam hoặc việt + nam.
- Metric token_quality trong preprocess metrics: tổng token, số token một ký tự, tỷ lệ và cảnh báo khi tỷ lệ thực tế chưa làm tròn vượt 10%.

F06 hiện hiển thị nguyên vẹn các token người, thông_tin và chia_sẻ trên 200 bài synthetic; không còn hiện tượng cắt tiền tố như “ng” + “ười” trong danh sách top token của lượt demo này.

### Top 15 TF trong F06 — chạy tại Mac

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

Top 15 TF-IDF của cùng lượt chạy cũng được in trong Terminal. Các token hàng đầu gồm về, chia_sẻ, mọi, người, mọi người, mình và thông_tin. Kết quả thuộc dữ liệu synthetic.

## 3. fbpipe demo và make demo

Đã triển khai và chạy end-to-end:
- fbpipe demo chạy synth --n 200 → preprocess --force → represent --skip-e5 → label-eval → store → analyze → viz → report.
- make demo gọi fbpipe demo.
- Dữ liệu demo đặt riêng trong data/demo; lệnh đặt giới hạn 90 giây và in thời gian mỗi stage, tổng thời gian và top 15 TF/TF-IDF từ F06.
- GitHub Actions xóa data/ trong runner sạch trước khi chạy smoke test demo offline có timeout 90 giây.
- Artifacts runtime gồm data/demo/, docs/figures/ và docs/REPORT_generated.md; xem git status trước khi commit để không vô tình đưa dữ liệu sinh ra vào Git.

## 4. Trạng thái theo phase

| Phase | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| 0 — Scaffold | Hoàn thành trong phạm vi | Package, config, schema, privacy, logging, CLI, metrics, .gitignore, pre-commit và CI |
| 1 — Collect | Một phần | Import/Synthetic chạy offline; Playwright auth/probe/crawl/resume bằng Facebook live chưa xác minh |
| 2 — Preprocess | Hoàn thành trong phạm vi rút gọn | S0–S11, ablation 3 cấu hình, Bronze → Silver Parquet, provenance và cảnh báo chất lượng token |
| 3 — Represent/Label | Hoàn thành trong phạm vi rút gọn | BoW/TF-IDF; E5 tùy chọn; đánh giá hiện dùng nhãn proxy, chưa có macro-F1 trên nhãn tay |
| 4 — Store/Benchmark | Hoàn thành trong phạm vi rút gọn | SQLite + FTS5, Parquet; benchmark 1k là bản clone, không phải 1.000 bài độc lập |
| 5 — Analyze | Demo pass | Metrics thống kê và nguồn |
| 6 — Viz/Report | Demo pass | 10 hình và báo cáo metrics sinh thành công ở CI và máy phát triển |

## 5. Tài liệu và phạm vi

- README.md: badge CI, kiến trúc Mermaid, Quickstart, 4 hình, bảng 7 mục tiêu theo SPEC §1, cảnh báo đạo đức, giới hạn và English summary.
- docs/REPORT.md: báo cáo nộp thủ công. Giữ nguyên phần Nhận định do người phát triển viết; không tự động ghi đè từ lệnh report.
- docs/REPORT_generated.md: đầu ra sinh tự động từ metrics hiện có.
- docs/STATUS.md: trạng thái dự án, bao gồm kết quả CI và lần chạy demo Mac mới nhất.
- .github/workflows/ci.yml: Ruff, format, test offline và demo end-to-end giới hạn 90 giây.

Chỉ mô tả lý thuyết, không triển khai theo SPEC §0b: MongoDB, Elasticsearch, PostgreSQL/DuckDB, HDFS/S3/Big Data, fastText tự huấn luyện, PhoBERT, Streamlit, NMF/BERTopic, capture–recapture, streaming/API demo.

## 6. Việc còn lại

1. Duyệt thủ công các hình trong docs/figures/F06_top_terms_tf_tfidf.png và kiểm tra tỷ lệ token một ký tự trên dữ liệu được phép sử dụng.
2. Nếu có file import được phép, xác minh provenance và chạy lại preprocess → represent → label-eval → store → analyze → viz → report trên dữ liệu đó; không gán nhãn nguồn Facebook nếu provenance không chứng minh.
3. Crawl live chưa được xác minh bằng phản hồi Facebook thật đã ẩn danh. Chỉ chạy auth/probe/crawl sau khi xác nhận quyền; dừng ngay khi có login wall, checkpoint, CAPTCHA hoặc hạn chế.
4. Muốn đánh giá mô hình có ý nghĩa thì cần nhãn tay được kiểm tra; proxy_labels=true không phải ground truth.
5. Notebook demo vẫn chưa được xác minh là có trong Git; chỉ tạo một notebook nếu còn trong phạm vi thời gian, không dựng lại các notebook đã bị loại.

## 7. Lệnh kiểm chứng

Từ root repository với .venv đã kích hoạt:

~~~bash
git pull origin main
ruff check .
ruff format --check src tests
pytest -m "not integration and not slow" -q
make demo
git diff --check
git status --short
~~~

Không stage/commit .env, .auth/, dữ liệu thật hoặc data/ runtime. Bản cập nhật STATUS này ghi nhận kết quả demo trên máy Mac; CI của nhánh tài liệu sẽ chạy lại sau khi đẩy PR.

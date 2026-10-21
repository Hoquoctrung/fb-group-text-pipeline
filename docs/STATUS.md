# Trạng thái dự án — Phase 0 + Phase 1

**Cập nhật:** 2026-10-21
**Phạm vi:** SPEC.md §0, §0b và DoD Phase 0–1. §0b được ưu tiên khi có mâu thuẫn.

> Báo cáo này chỉ ghi nhận những gì đã có bằng chứng từ output Terminal, danh sách file Git và ảnh GitHub Actions do người phát triển cung cấp. “Đã có code” không đồng nghĩa với “đã kiểm thử end-to-end”. Không dùng synthetic làm kết quả nghiên cứu thực tế.

## 1. File hiện có theo module

### Root và cấu hình

- `.env.example`
- `.gitignore`
- `.pre-commit-config.yaml`
- `LICENSE`
- `Makefile`
- `README.md`
- `pyproject.toml`
- `configs/default.yaml`
- `.github/workflows/ci.yml`

### Source: `src/fbpipe/`

- `__init__.py`
- `cli.py` — các lệnh `auth`, `probe`, `synth`, `import`, `crawl`, `validate`
- `config.py`
- `logging_utils.py`
- `metrics.py`
- `privacy.py`
- `schema.py`

### Collect: `src/fbpipe/collect/`

- `__init__.py`
- `base.py`
- `checkpoint.py`
- `graphql_parser.py`
- `import_collector.py`
- `playwright_collector.py`
- `synthetic.py`

### Resources

- `resources/en_extra_stopwords.txt`
- `resources/vi_ambiguous.txt`
- `resources/vi_stopwords.txt`
- `resources/vi_teencode.tsv`

### Tests và fixtures

- `tests/conftest.py`
- `tests/test_checkpoint.py`
- `tests/test_cli.py`
- `tests/test_graphql_parser.py`
- `tests/test_import_collector.py`
- `tests/test_privacy.py`
- `tests/test_schema.py`
- `tests/test_synthetic.py`
- `tests/fixtures/README.md`
- `tests/fixtures/graphql_sample.txt` — fixture tự tạo, không phải schema Facebook thật

### Docs và dữ liệu

- `docs/ARCHITECTURE.md`
- `docs/CHALLENGES.md`
- `docs/DECISIONS.md`
- `docs/ETHICS.md`
- `docs/REPORT.md`
- `docs/SPEC.md`
- `docs/STATUS.md` — tài liệu này
- `data/sample/.gitkeep`
- Dữ liệu chạy thử từng được tạo tại `data/bronze/` và `data/metrics/`, nhưng đã được `.gitignore` loại khỏi Git. Output smoke test import được ghi trong `/tmp/`.

### Phần không có trong danh sách file đã commit

- Chưa có notebook demo trong danh sách file Git đã kiểm tra.
- Chưa có các module Preprocess, Represent, Store, Viz và trình sinh báo cáo tự động hoàn chỉnh cho các phase sau.
- Không có DOM parser fallback, API demo hoặc streaming simulation — phù hợp ngoại lệ phạm vi §0b.

## 2. DoD Phase 0 — Scaffold

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc lý do |
|---|---|---|
| Scaffold package, cấu hình, schema, privacy, logging, CLI, metrics | [x] Có | File tương ứng hiện diện; package được cài editable trong `.venv`. |
| `.gitignore` bảo vệ `.env`, `.auth/` và dữ liệu sinh ra | [x] Đã kiểm tra | `git check-ignore -v .env .auth/state.json data/bronze/raw_posts.jsonl` cho kết quả ignore đúng. |
| Unit tests chạy được | [x] Đã kiểm tra | `pytest -q` cho kết quả `26 passed`. |
| Ruff lint sạch | [x] Đã kiểm tra | `ruff check src tests` trả `All checks passed!`. |
| Ruff format sạch | [x] Đã kiểm tra | `ruff format --check src tests` trả `23 files already formatted`. |
| CLI hiển thị lệnh | [x] Đã kiểm tra | `fbpipe --help` hiển thị `auth`, `probe`, `synth`, `import`, `crawl`, `validate`. |
| CI trên GitHub | [x] Đã quan sát | Ảnh tab Actions cho thấy workflow CI của commit `6c17148` thành công (dấu check xanh). |
| `docs/ETHICS.md` và pre-commit config tồn tại | [x] Có | Cả hai file nằm trong danh sách file đã commit. |
| Các hook pre-commit đã chạy thành công | [ ] Chưa xác minh | Chưa có output `pre-commit run --all-files`; có file cấu hình không đồng nghĩa hook đã chạy. |

## 3. DoD Phase 1 — Collect

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc lý do |
|---|---|---|
| `ImportCollector` đọc CSV/JSONL | [x] Đã kiểm tra | Test `tests/test_import_collector.py` nằm trong suite 26 test pass; smoke test CSV import 2 bài, bỏ qua 0 dòng lỗi. |
| Bronze JSONL được validate | [x] Đã kiểm tra | `fbpipe validate /tmp/fbpipe_import_smoke.jsonl` trả `{"valid": 2, "invalid": 0}`. |
| `SyntheticCollector` deterministic với seed cố định | [x] Đã kiểm tra | Unit test synthetic pass trong suite 26 test. |
| Sinh 200 bài synthetic và validate | [x] Đã kiểm tra | `fbpipe synth --n 200`; `fbpipe validate data/bronze/synthetic.jsonl` trả 200 valid, 0 invalid. Đây là dữ liệu synthetic, không phải dữ liệu nhóm Facebook. |
| Parser đọc nhiều JSON value nối nhau và fixture tổng quát | [x] Đã kiểm tra ở fixture | `tests/test_graphql_parser.py` pass. Fixture tự tạo, không xác nhận key path của Facebook. |
| Có `TODO(real-sample)` cho parser | [x] Có | Parser và tài liệu ethics nêu rõ chưa được xác minh bằng mẫu probe thật. |
| Checkpoint save/load và `seen_ids` | [x] Đã kiểm tra ở unit test | `pytest -v tests/test_checkpoint.py`: 3 passed. |
| CLI có tùy chọn `crawl --resume` | [x] Đã kiểm tra | `fbpipe crawl --help` hiển thị `--resume`; test offline của `tests/test_cli.py` nằm trong tổng 26 test pass. |
| Resume không trùng khi chạy Playwright end-to-end | [ ] Chưa xác minh | Chưa chạy collector với phiên đăng nhập và phản hồi thật; các test hiện tại chưa chứng minh hành vi end-to-end hoặc tình huống crash giữa ghi Bronze và lưu checkpoint. |
| Playwright auth/probe/crawl chạy end-to-end | [ ] Chưa xác minh | Đã kiểm tra `fbpipe probe --help` và `fbpipe crawl --help`, nhưng chưa chạy `auth`, `probe` hoặc `crawl` thực tế. Chưa có bằng chứng trình duyệt và session state hoạt động trong phiên thật. |
| Dừng an toàn khi gặp login wall/checkpoint/restriction | [~] Có code, chưa xác minh live | Logic phát hiện và `CollectionBlocked` có trong collector; chưa thử nghiệm trên phiên thật. Không được cố vượt qua hạn chế/captcha. |
| Parser trích xuất bài Facebook thực tế | [ ] Chưa xác minh | Chưa có `probe_report.md` cùng mẫu phản hồi đã ẩn danh; không được đoán schema nội bộ. |
| Bảng 1 đủ 5 kỹ thuật theo ngoại lệ §0b | [x] Có trong báo cáo | `docs/REPORT.md` mô tả File import, Web scraping, Crawling, API và Streaming. API/Streaming chỉ mô tả, không có demo code theo §0b. |
| `docs/CHALLENGES.md` có ít nhất 10 hàng | [x] Có nội dung | Bảng hiện có 15 thách thức; các mục chưa đo được được ghi `pending`, không tự điền số liệu giả. |

## 4. TODO còn lại

### Cần làm để hoàn tất xác minh Phase 1

1. **Xác nhận quyền thu thập** và xác định nhóm công khai/riêng tư trước khi mở phiên crawl. Chỉ chạy với quyền cho phép; không né login wall, checkpoint hoặc captcha.
2. Kiểm tra browser install và luồng `fbpipe auth` bằng tài khoản của chính người phát triển; không chia sẻ hoặc commit `.auth/state.json`.
3. Khi đã được phép, chạy `fbpipe probe`, kiểm tra thủ công việc ẩn danh hóa, rồi lưu `probe_report.md` và mẫu đã loại bỏ định danh ở vị trí local/gitignored. Chỉ chỉnh parser dựa vào key path quan sát được.
4. Sau khi parser có mẫu thật, kiểm thử `crawl` và `crawl --resume` trong điều kiện được phép; xác nhận không ghi trùng khi tiếp tục và ghi nhận `stop_reason`/metrics. Hiện tại chưa được tuyên bố đã crawl Facebook thành công.
5. Chạy `pre-commit run --all-files` và lưu kết quả nếu muốn xác nhận các hook hoạt động.

### TODO theo phạm vi dự án §0b, không thuộc DoD Phase 0–1

1. Tạo **một notebook demo** (không tạo lại 7 notebook đã bị loại).
2. Triển khai Preprocess S0–S11 bản gọn và ablation 4 cấu hình.
3. Triển khai BoW, TF-IDF, E5 và macro-F1 trên tập nhãn tay khoảng 100 bài.
4. Triển khai SQLite và Parquet + DuckDB; benchmark tại 1k và 10k tài liệu.
5. Sinh các hình F01, F03, F06, F07, F09, F10, F11, F13, F14, F15.
6. Hoàn thiện báo cáo tự động; phần **Nhận định** giữ placeholder để Trung tự viết.
7. Không triển khai MongoDB, Elasticsearch, Postgres, Docker, Streamlit, `stream_sim`, `api_demo_hn`, NMF/BERTopic hoặc capture–recapture theo §0b; chỉ mô tả lý thuyết nơi phù hợp.

## 5. Lệnh kiểm chứng

Chạy các lệnh từ root `fb-group-text-pipeline` và trong virtual environment `.venv`.

### Môi trường, test và chất lượng code

```bash
python --version
python -m pip show fb-group-text-pipeline
ruff check src tests
ruff format --check src tests
pytest -q
pytest -v tests/test_checkpoint.py
pytest -q tests/test_cli.py tests/test_graphql_parser.py tests/test_import_collector.py tests/test_synthetic.py
```

### CLI và collector offline

```bash
fbpipe --help
fbpipe probe --help
fbpipe crawl --help
fbpipe import --help
fbpipe synth --n 200
fbpipe validate data/bronze/synthetic.jsonl
```

### Smoke test import CSV

```bash
cat > /tmp/fbpipe_import_smoke.csv <<'CSV'
post_id,author,created_at,text,reactions,comments_count
smoke-001,test-user,2026-10-21T09:00:00+07:00,"Bài kiểm thử import đầu tiên",3,1
smoke-002,test-user-2,2026-10-21T09:05:00+07:00,"Kiểm tra CSV và validate",5,0
CSV

FBPIPE_SALT=fbpipe-local-test-salt fbpipe import /tmp/fbpipe_import_smoke.csv \
  --output /tmp/fbpipe_import_smoke.jsonl --group-id smoke-group
fbpipe validate /tmp/fbpipe_import_smoke.jsonl
```

Kết quả đã quan sát lần trước: `Imported 2 posts; skipped 0 invalid rows` và `{"valid": 2, "invalid": 0}`.

### Kiểm tra secret/data ignore và Git

```bash
git check-ignore -v .env .auth/state.json data/bronze/raw_posts.jsonl
git status --short
git log -1 --oneline
git remote -v
```

Kết quả đã quan sát: repository riêng đúng ở thư mục dự án, commit đầu tiên `6c17148`, `main` theo dõi `origin/main`, working tree sạch tại thời điểm kiểm tra; dữ liệu chạy thử trong `data/bronze/` và `data/metrics/` được ignore. Không commit `.env`, `.auth/`, sample/probe chưa duyệt hoặc dữ liệu Facebook thật.

### Kiểm tra CI

Mở GitHub repository → **Actions**. Bằng chứng đã quan sát là workflow CI của commit `6c17148` có dấu check xanh. Khi có commit mới, cần xem run tương ứng với commit mới đó; không suy ra CI của tương lai từ kết quả cũ.

### Kiểm tra live (chưa chạy)

Chỉ sau khi có quyền thu thập và đã đọc `docs/ETHICS.md`, hãy chạy `fbpipe auth` rồi `fbpipe probe`. **Không chạy `fbpipe crawl` hoặc `fbpipe crawl --resume` chỉ để đánh dấu DoD** nếu chưa có quyền hoặc chưa sẵn sàng xử lý dữ liệu. Nếu gặp restriction, dừng lại; không thử né chặn.

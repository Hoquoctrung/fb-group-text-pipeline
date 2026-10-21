# Trạng thái dự án — Phase 0 đến Phase 4 (phạm vi rút gọn)

**Cập nhật:** 2026-10-21  
**Phạm vi:** `docs/SPEC.md` §0, §0b và các DoD Phase 0–4 trong phạm vi rút gọn. Phase 2 dùng ablation 3 cấu hình; Phase 3–4 chỉ triển khai BoW/TF-IDF/E5 tùy chọn, labeling, SQLite/FTS5, Parquet và benchmark 1k.

> Báo cáo này chỉ ghi nhận những gì đã có bằng chứng từ output Terminal, danh sách file Git và ảnh GitHub Actions do người phát triển cung cấp. “Đã có code” không đồng nghĩa với “đã kiểm thử end-to-end”. Không dùng synthetic làm kết quả nghiên cứu thực tế.

### Snapshot mới nhất (sau triển khai Phase 3–4; chưa commit)

- `pytest -q`: **61 passed** trên máy phát triển.
- `ruff check src tests`, `ruff format --check src tests` và `pre-commit run --all-files`: **đều pass**. Pylance Problems được người phát triển xác nhận là **0**.
- `fbpipe represent --skip-e5`: 200 documents; BoW 148 chiều, TF-IDF 148 chiều; sau cài `.[embed]`, `fbpipe represent --force` chạy E5 và báo `E5=available`.
- `fbpipe label-sample --n 200`: xuất 200 dòng vào `data/labels/to_label.csv`. Chưa có bằng chứng người phát triển đã điền nhãn tay; `fbpipe label-eval` vì vậy dùng nhãn yếu và ghi `proxy_labels=true`. Các điểm macro-F1 được in ra chỉ là chẩn đoán theo nhãn proxy, không phải đánh giá có nhãn chuẩn.
- `fbpipe store`: đã lưu 200 dòng Silver vào SQLite (`data/fbpipe.db`) và Parquet (`data/store/documents.parquet`).
- `fbpipe bench-storage --n 1000 --iterations 20`: đã hoàn tất benchmark SQLite FTS5/Parquet trên 1.000 bản ghi clone; metrics ở `data/metrics/bench_storage.json`. Đây là dữ liệu benchmark nhân bản, không phải 1.000 bài Facebook thật.
- Phase 3–4 đang ở trạng thái **đã chạy kiểm thử trên máy phát triển, chờ rà soát và commit**. Dữ liệu sinh ra trong `data/` không được stage/commit.

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
- `cli.py` — các lệnh `auth`, `probe`, `synth`, `import`, `crawl`, `preprocess`, `represent`, `label-sample`, `label-eval`, `store`, `bench-storage`, `validate`
- `config.py`
- `logging_utils.py`
- `metrics.py`
- `privacy.py`
- `schema.py`

### Preprocess: `src/fbpipe/preprocess/`

- `__init__.py`
- `steps.py` — transforms S0–S11, fallback khi thiếu optional NLP corpora
- `pipeline.py` — Bronze JSONL → Silver Parquet, metrics, ablation 3 cấu hình

### Collect: `src/fbpipe/collect/`

- `__init__.py`
- `base.py`
- `checkpoint.py`
- `graphql_parser.py`
- `import_collector.py`
- `playwright_collector.py`
- `synthetic.py`

### Represent: `src/fbpipe/represent/`

- `__init__.py`
- `pipeline.py` — BoW, TF-IDF, E5 tùy chọn, cache embedding và metrics
- `labeling.py` — lấy mẫu nhãn, nhãn yếu theo luật, proxy-label evaluation

### Storage: `src/fbpipe/storage/`

- `__init__.py`
- `sqlite_store.py` — SQLite + FTS5, upsert và truy vấn
- `parquet_store.py` — lưu bản Parquet
- `benchmark.py` — benchmark SQLite/Parquet trên bản ghi clone

### Resources

- `resources/en_extra_stopwords.txt`
- `resources/vi_ambiguous.txt`
- `resources/vi_stopwords.txt`
- `resources/vi_teencode.tsv`
- `resources/domain_stopwords.txt` — danh sách duyệt tay; dòng `# candidate:` chỉ là gợi ý, chưa tự động áp dụng

### Tests và fixtures

- `tests/conftest.py`
- `tests/test_checkpoint.py`
- `tests/test_cli.py`
- `tests/test_graphql_parser.py`
- `tests/test_import_collector.py`
- `tests/test_privacy.py`
- `tests/test_schema.py`
- `tests/test_synthetic.py`
- `tests/test_preprocess.py` — bảng input/output cho S0–S11 và test pipeline Parquet có điều kiện
- `tests/test_represent.py` — kiểm thử BoW/TF-IDF/E5 tùy chọn
- `tests/test_labeling.py` — kiểm thử lấy mẫu và nhãn yếu
- `tests/test_storage.py` — kiểm thử SQLite FTS5, Parquet và benchmark
- `tests/test_phase34_cli.py` — kiểm thử CLI Phase 3–4
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
- Phase 3–4 có bản triển khai tối thiểu và đã được kiểm tra trên máy phát triển như ghi ở các mục dưới. Viz, phân tích chủ đề, dashboard và report automation đầy đủ vẫn thuộc phase sau.
- Không có DOM parser fallback, API demo hoặc streaming simulation — phù hợp ngoại lệ phạm vi §0b.

## 2. DoD Phase 0 — Scaffold

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc lý do |
|---|---|---|
| Scaffold package, cấu hình, schema, privacy, logging, CLI, metrics | [x] Có | File tương ứng hiện diện; package được cài editable trong `.venv`. |
| `.gitignore` bảo vệ `.env`, `.auth/` và dữ liệu sinh ra | [x] Đã kiểm tra | `git check-ignore -v .env .auth/state.json data/bronze/raw_posts.jsonl` cho kết quả ignore đúng. |
| Unit tests chạy được | [x] Đã kiểm tra | `pytest -q` gần nhất cho kết quả `43 passed` sau khi hoàn thành Phase 2. |
| Ruff lint sạch | [x] Đã kiểm tra | `ruff check src tests` trả `All checks passed!`. |
| Ruff format sạch | [x] Đã kiểm tra | `ruff format --check src tests` trả `27 files already formatted`. |
| CLI hiển thị lệnh | [x] Đã kiểm tra | `fbpipe --help` hiển thị các lệnh Phase 0–2 gồm `auth`, `probe`, `synth`, `import`, `crawl`, `preprocess`, `validate`. |
| CI trên GitHub | [x] Đã quan sát | Ảnh tab Actions cho thấy workflow CI của commit `6c17148` thành công (dấu check xanh). |
| `docs/ETHICS.md` và pre-commit config tồn tại | [x] Có | Cả hai file nằm trong danh sách file đã commit. |
| Các hook pre-commit đã chạy thành công | [x] Đã kiểm tra | `pre-commit run --all-files`: các hook Ruff, format, end-of-files, trailing-whitespace, YAML, file-size và secret detection đều pass. |

## 3. DoD Phase 1 — Collect

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc lý do |
|---|---|---|
| `ImportCollector` đọc CSV/JSONL | [x] Đã kiểm tra | Test `tests/test_import_collector.py` nằm trong suite hiện tại `43 passed`; smoke test CSV import 2 bài, bỏ qua 0 dòng lỗi. |
| Bronze JSONL được validate | [x] Đã kiểm tra | `fbpipe validate /tmp/fbpipe_import_smoke.jsonl` trả `{"valid": 2, "invalid": 0}`. |
| `SyntheticCollector` deterministic với seed cố định | [x] Đã kiểm tra | Unit test synthetic nằm trong suite hiện tại `43 passed`. |
| Sinh 200 bài synthetic và validate | [x] Đã kiểm tra | `fbpipe synth --n 200`; `fbpipe validate data/bronze/synthetic.jsonl` trả 200 valid, 0 invalid. Đây là dữ liệu synthetic, không phải dữ liệu nhóm Facebook. |
| Parser đọc nhiều JSON value nối nhau và fixture tổng quát | [x] Đã kiểm tra ở fixture | `tests/test_graphql_parser.py` pass. Fixture tự tạo, không xác nhận key path của Facebook. |
| Có `TODO(real-sample)` cho parser | [x] Có | Parser và tài liệu ethics nêu rõ chưa được xác minh bằng mẫu probe thật. |
| Checkpoint save/load và `seen_ids` | [x] Đã kiểm tra ở unit test | `pytest -v tests/test_checkpoint.py`: 3 passed. |
| CLI có tùy chọn `crawl --resume` | [x] Đã kiểm tra | `fbpipe crawl --help` hiển thị `--resume`; test offline của `tests/test_cli.py` nằm trong suite hiện tại 43 test pass. |
| Resume không trùng khi chạy Playwright end-to-end | [ ] Chưa xác minh | Chưa chạy collector với phiên đăng nhập và phản hồi thật; các test hiện tại chưa chứng minh hành vi end-to-end hoặc tình huống crash giữa ghi Bronze và lưu checkpoint. |
| Playwright auth/probe/crawl chạy end-to-end | [ ] Chưa xác minh | Đã kiểm tra `fbpipe probe --help` và `fbpipe crawl --help`, nhưng chưa chạy `auth`, `probe` hoặc `crawl` thực tế. Chưa có bằng chứng trình duyệt và session state hoạt động trong phiên thật. |
| Dừng an toàn khi gặp login wall/checkpoint/restriction | [~] Có code, chưa xác minh live | Logic phát hiện và `CollectionBlocked` có trong collector; chưa thử nghiệm trên phiên thật. Không được cố vượt qua hạn chế/captcha. |
| Parser trích xuất bài Facebook thực tế | [ ] Chưa xác minh | Chưa có `probe_report.md` cùng mẫu phản hồi đã ẩn danh; không được đoán schema nội bộ. |
| Bảng 1 đủ 5 kỹ thuật theo ngoại lệ §0b | [x] Có trong báo cáo | `docs/REPORT.md` mô tả File import, Web scraping, Crawling, API và Streaming. API/Streaming chỉ mô tả, không có demo code theo §0b. |
| `docs/CHALLENGES.md` có ít nhất 10 hàng | [x] Có nội dung | Bảng hiện có 15 thách thức; các mục chưa đo được được ghi `pending`, không tự điền số liệu giả. |

## 4. Phase 2 — Preprocess (code được thêm trong bản cập nhật hiện tại)

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc giới hạn |
|---|---|---|
| S0–S11 có transforms độc lập `name` + `apply(doc)` | [x] Có code | `src/fbpipe/preprocess/steps.py`; có đường lui khi thiếu optional NLP packages/corpora. |
| Test dạng bảng input/output cho từng bước S0–S11 | [x] Đã chạy | Các test bảng nằm trong `tests/test_preprocess.py`. |
| Stem/lemma chỉ cho token tiếng Anh | [x] Có code | Chỉ xử lý token ASCII đủ điều kiện có trong NLTK English words corpus; tiếng Việt giữ nguyên. Không tự tải corpus. |
| Ablation đúng 3 cấu hình | [x] Có code | `A0_strip_only`, `A1_clean_and_tokenize`, `A2_full_s0_s11`; khác với TODO cũ 4 cấu hình. |
| Đọc `data/bronze/*.jsonl` và lệnh `fbpipe preprocess` | [x] Đã kiểm tra help | `python -m fbpipe.cli preprocess --help` hiển thị `--config`, `--input-dir`, `--output`, `--force`. |
| Sinh `data/silver/documents.parquet` và `data/metrics/preprocess.json` | [x] Đã chạy end-to-end | `fbpipe preprocess`: `Preprocessed 200 posts`; `invalid records: 0`. Tệp Parquet 47 KB, metrics JSON 2.7 KB. |
| Metrics funnel, thời gian bước, OOV, teencode, code-mixed và domain-stopword candidates | [x] Có code | OOV là `null`/không có top terms khi NLTK English words corpus không khả dụng; không bịa số liệu. |
| Unit tests sau khi hoàn thành Phase 2 | [x] Đã xác minh trên máy phát triển | `pytest -q`: `43 passed` (không skip). |
| Ruff, format và pre-commit sau thay đổi này | [x] Đã xác minh trên máy phát triển | `ruff check src tests`: `All checks passed!`; `ruff format --check src tests`: `27 files already formatted`; `pre-commit run --all-files`: tất cả hook pass. |

### Kết quả thực tế đã quan sát ở Phase 2

- Đầu vào: `data/bronze/synthetic.jsonl` — **200 bài synthetic**, không phải dữ liệu Facebook thật.
- Đầu ra: `data/silver/documents.parquet` (**47 KB**) và `data/metrics/preprocess.json` (**2.7 KB**).
- Kiểm tra Parquet: **200 dòng**, 32 cột; metrics ghi `n_invalid_records = 0`.
- Funnel: 200 đầu vào → 53 sau dedup → 53 sau lọc spam → 53 sau lọc bài ngắn → 53 `keep`; 147 bản ghi được đánh dấu duplicate. Parquet giữ 200 dòng để lưu cả nhãn chất lượng, không chỉ các dòng `keep=true`.
- NLTK English reference corpus không có trong lần chạy: `oov_reference_available = false`, `english_morphology_enabled = false`, `oov_ratio_english = null`. Đây là trạng thái được ghi rõ, không phải số liệu OOV bằng 0.
- Runtime ghi nhận `pipeline_seconds = 2.208839` trên máy phát triển trong lần chạy này; chỉ là số đo của lần chạy, không phải benchmark tổng quát.
- Commit Phase 2: `e688a95 feat: add Phase 2 text preprocessing pipeline`; output Git trước đó cho thấy `HEAD -> main` và `origin/main` cùng trỏ commit này.

## 5. Phase 3 — Represent & Labeling

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc giới hạn |
|---|---|---|
| BoW trên `tokens_nostop`, sparse `.npz`, vocabulary và `doc_ids` | [x] Đã chạy | `fbpipe represent --skip-e5`: 200 documents, BoW 148 dimensions. Artifacts nằm dưới `data/gold/`. |
| TF-IDF với cấu hình của pipeline | [x] Đã chạy | Cùng lần chạy: TF-IDF 148 dimensions. |
| E5 import lười, `text_clean`, prefix `query: `, L2 normalization và cache `.npy` | [x] Đã chạy trên máy phát triển | Sau `python -m pip install -e ".[embed]"`, `fbpipe represent --force` báo `E5=available`; model được tải từ Hugging Face. Khi thiếu dependency/lỗi tải, code có nhánh cảnh báo và bỏ qua E5. |
| `label-sample` tạo CSV theo taxonomy | [x] Đã chạy | `fbpipe label-sample --n 200`: 200 dòng được tạo tại `data/labels/to_label.csv`; taxonomy `hoi_dap`, `chia_se`, `thong_bao`, `tim_kiem_tuyen_dung`, `quang_cao_spam`, `khac`. |
| `label-eval` báo rõ nhãn proxy nếu chưa có nhãn tay | [x] Đã chạy | Terminal hiển thị cảnh báo và `proxy_labels=true`; hiện chưa có bằng chứng nhãn tay đã được nhập. Không trình bày các điểm số theo proxy như macro-F1 có ground truth. |
| Unit tests Phase 3–4 | [x] Đã chạy | Tổng suite hiện tại: `61 passed`. |

## 6. Phase 4 — Store & Benchmark

| DoD / tiêu chí | Trạng thái | Bằng chứng hoặc giới hạn |
|---|---|---|
| SQLite làm backend duy nhất ngoài Parquet | [x] Đã chạy | `fbpipe store`: 200 Silver rows được lưu vào `data/fbpipe.db`. |
| Full-text search | [x] Có code/test | SQLite dùng FTS5; test storage nằm trong `tests/test_storage.py`. |
| Parquet store | [x] Đã chạy | `fbpipe store`: 200 rows, `data/store/documents.parquet` được ghi. |
| Benchmark 1.000 bản ghi, 20 iterations | [x] Đã chạy | `fbpipe bench-storage --n 1000 --iterations 20`; kết quả tại `data/metrics/bench_storage.json`. Các dòng benchmark được nhân bản và có cờ đánh dấu; không đại diện dữ liệu thật. |
| Ruff, format và pre-commit sau Phase 3–4 | [x] Đã chạy | `ruff check src tests`: All checks passed; format pass; mọi hook `pre-commit run --all-files` pass. |
| Toàn bộ test suite | [x] Đã chạy | `pytest -q`: `61 passed` trong 6.08 giây trong lần xác minh gần nhất được cung cấp. |

## 7. TODO còn lại

### Collect — vẫn chưa xác minh live

1. **Xác nhận quyền thu thập** và nhóm công khai/riêng tư trước khi mở phiên crawl. Chỉ chạy khi được phép; không né login wall, checkpoint hoặc captcha.
2. Chưa có bằng chứng `auth`, `probe`, `crawl` và `crawl --resume` đã chạy end-to-end bằng phiên Facebook thật.
3. Chưa có `probe_report.md` cùng mẫu response thật đã ẩn danh. Chỉ chỉnh parser bằng key path quan sát được; hiện chưa được tuyên bố đã crawl Facebook thành công.

### Phase 3 — labeling/evaluation

1. Người phát triển cần đọc mẫu dữ liệu, chốt taxonomy và điền nhãn tay vào `data/labels/to_label.csv`; tới lúc đó `proxy_labels=true` vẫn là nguồn nhãn của đánh giá hiện tại.
2. Mục tiêu macro-F1 trên khoảng 100 nhãn tay theo SPEC chưa được xác minh vì chưa có ground-truth labels.

### Phần scope còn lại của dự án

1. Tạo **một notebook demo** (không tạo lại bảy notebook đã bị loại).
2. Sinh những hình được giữ trong phạm vi rút gọn: F01, F03, F06, F07, F09, F10, F11, F13, F14, F15.
3. Hoàn thiện báo cáo tự động; phần **Nhận định** giữ placeholder để Trung tự viết dựa trên dữ liệu được phép sử dụng.
4. Không triển khai MongoDB, Elasticsearch, Postgres, Docker, DuckDB, Streamlit, `stream_sim`, `api_demo_hn`, NMF/BERTopic hoặc capture–recapture theo §0b; chỉ mô tả lý thuyết nơi phù hợp.
5. Phase 3–4 **chưa được commit/push** ở thời điểm snapshot này; trước commit, xem `git diff --cached --check`, danh sách staged và xác nhận không có `data/`, `.env` hoặc `.auth/`.

## 8. Lệnh kiểm chứng

Chạy các lệnh từ root `fb-group-text-pipeline` và trong virtual environment `.venv`.

### Phase 3–4 — đã được chạy; lệnh lặp lại khi cần

```bash
fbpipe represent --skip-e5
# E5 tùy chọn; cần cài extra embed và có mạng ở lần tải model đầu tiên
python -m pip install -e ".[embed]"
fbpipe represent --force
fbpipe label-sample --n 200
# Chỉ sau khi tự điền nhãn tay mới diễn giải đánh giá như nhãn ground truth
fbpipe label-eval
fbpipe store
fbpipe bench-storage --n 1000 --iterations 20
ruff check src tests
ruff format --check src tests
pre-commit run --all-files
pytest -q
```


### Môi trường, test và chất lượng code

```bash
python --version
python -m pip show fb-group-text-pipeline
ruff check src tests
ruff format --check src tests
pre-commit run --all-files
pytest -q
pytest -v tests/test_checkpoint.py
pytest -q tests/test_cli.py tests/test_graphql_parser.py tests/test_import_collector.py tests/test_synthetic.py
```

### Phase 2 — Preprocess

Sau khi cài dependency trên môi trường phát triển:

```bash
python -m pip install -e ".[dev,crawl,nlp]"
ruff check src tests
ruff format --check src tests
pre-commit run --all-files
pytest -q
fbpipe preprocess --help
fbpipe preprocess
```

Sau khi chạy, kiểm tra `data/silver/documents.parquet` và `data/metrics/preprocess.json`. Nếu dữ liệu Bronze hoặc resources đã thay đổi, lệnh chạy lại; `--force` bỏ qua kiểm tra up-to-date.

### CLI và collector offline

```bash
fbpipe --help
fbpipe probe --help
fbpipe crawl --help
fbpipe import --help
fbpipe preprocess --help
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

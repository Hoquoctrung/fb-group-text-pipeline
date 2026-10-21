# FB Group Text Pipeline

Pipeline học thuật để thu thập **dữ liệu được phép sử dụng**, chuẩn hóa văn bản và chuẩn bị biểu diễn/lưu trữ nội dung nhóm Facebook.

> **Phạm vi code tối thiểu:** Collect, Preprocess, BoW/TF-IDF, tùy chọn E5, CSV gán nhãn, SQLite/FTS5 và Parquet. Các giới hạn/ngoại lệ được ghi trong `docs/SPEC.md` và `docs/STATUS.md`.

## Quy tắc an toàn

- Chỉ thu thập khi có quyền/cho phép phù hợp; đọc `docs/ETHICS.md` trước khi crawl.
- Không vượt CAPTCHA, login wall, checkpoint hay cơ chế kiểm soát truy cập. Nếu bị chặn, dừng.
- Không commit `.env`, `.auth/`, dữ liệu thật hoặc phản hồi chưa ẩn danh.
- Parser chỉ dùng heuristic tổng quát và fixture tự tạo cho đến khi có mẫu `probe` thật đã ẩn danh. Xem `TODO(real-sample)`.
- Không coi dữ liệu synthetic, bootstrap clone hoặc weak/proxy labels là ground truth.

## Quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,crawl,nlp]"
cp .env.example .env
# Sửa FBPIPE_SALT trong .env bằng secret ngẫu nhiên do bạn tạo
fbpipe --help
fbpipe synth --n 200
fbpipe validate data/bronze/synthetic.jsonl
fbpipe preprocess
pytest -q
```

Cài Chromium cho Playwright khi cần:

```bash
playwright install chromium
```

## Phase 3–4: biểu diễn, gán nhãn và lưu trữ

```bash
fbpipe represent --skip-e5
fbpipe label-sample --n 200
# Mở data/labels/to_label.csv và điền nhãn vào cột label.
fbpipe label-eval
fbpipe store
fbpipe bench-storage --n 1000 --iterations 20
```

BoW/TF-IDF chạy với các dependency core. E5 là tùy chọn, import lười:

```bash
python -m pip install -e ".[embed]"
fbpipe represent --force
```

Nếu `sentence-transformers` thiếu hoặc model không tải được, chương trình cảnh báo và bỏ qua E5 nhưng vẫn tạo BoW/TF-IDF. Nếu chưa có nhãn tay, `label-eval` dùng luật heuristic và ghi `proxy_labels=true`; chỉ số này mang tính chẩn đoán, không đại diện cho đánh giá nhãn người.

`fbpipe store` ghi cả SQLite/FTS5 (`data/fbpipe.db`) và Parquet (`data/store/documents.parquet`). Benchmark dùng 1.000 bản sao bootstrap có đánh dấu, không phải 1.000 bài thật, và không tác động database chính.

## Phase 1: thu thập

```bash
fbpipe auth --config configs/default.yaml
fbpipe probe --config configs/default.yaml
fbpipe crawl --config configs/default.yaml
fbpipe import ./allowed-data.jsonl --group-id 230048322891238
fbpipe synth --n 1000
```

`crawl` mặc định bị khóa cho đến khi bạn đã đọc ethics và chủ động đặt `compliance.acknowledged: true` trong cấu hình. Lệnh `probe` lưu mẫu JSON đã ẩn danh theo heuristic; vẫn phải duyệt kỹ trước khi chia sẻ.

## Lưu ý về trạng thái

- Các đầu ra sinh ra dưới `data/` được gitignored.
- PostgreSQL, MongoDB, Elasticsearch, DuckDB, fastText/Word2Vec, PhoBERT, Docker, Streamlit, các biểu đồ Phase 5 và báo cáo tự động đầy đủ không nằm trong phạm vi rút gọn hiện tại.
- Xem `docs/STATUS.md` để biết rõ mục nào đã test, mục nào cần xác minh end-to-end.

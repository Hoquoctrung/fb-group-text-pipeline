# FB Group Text Pipeline

Pipeline học thuật để thu thập **dữ liệu được phép sử dụng**, chuẩn hóa văn bản và chuẩn bị phân tích nội dung nhóm Facebook.

> **Phạm vi hiện tại:** Phase 0 + Phase 1, theo §0b trong `docs/SPEC.md`. Collector trình duyệt là bản tối thiểu; parser Facebook chưa được xác minh bằng mẫu thật.

## Quy tắc an toàn

- Chỉ thu thập khi có quyền/cho phép phù hợp; đọc `docs/ETHICS.md` trước khi crawl.
- Không vượt CAPTCHA, login wall, checkpoint hay cơ chế kiểm soát truy cập. Nếu bị chặn, dừng.
- Không commit `.env`, `.auth/`, dữ liệu thật hoặc phản hồi chưa ẩn danh.
- Parser chỉ dùng heuristic tổng quát và fixture tự tạo cho đến khi có mẫu `probe` thật đã ẩn danh. Xem `TODO(real-sample)`.

## Quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,crawl]"
cp .env.example .env
# Sửa FBPIPE_SALT trong .env bằng secret ngẫu nhiên do bạn tạo
fbpipe --help
fbpipe synth --n 200
fbpipe validate data/bronze/synthetic.jsonl
pytest -q
```

Cài Chromium cho Playwright khi cần:

```bash
playwright install chromium
```

## CLI Phase 1

```bash
fbpipe auth --config configs/default.yaml
fbpipe probe --config configs/default.yaml
fbpipe crawl --config configs/default.yaml
fbpipe import ./allowed-data.jsonl --group-id 230048322891238
fbpipe synth --n 1000
```

`crawl` mặc định bị khóa cho đến khi bạn đã đọc ethics và chủ động đặt `compliance.acknowledged: true` trong cấu hình. Lệnh `probe` lưu mẫu JSON đã ẩn danh theo heuristic; vẫn phải duyệt kỹ trước khi chia sẻ.

## Trạng thái

- Có: schema, privacy helpers, JSONL/CSV import, synthetic fixtures, passive Playwright response listener, checkpoint, CLI, unit tests, CI.
- Chưa có ở Phase 0 + 1: preprocess, representations, SQLite/Parquet-DuckDB storage, benchmark, visualization và báo cáo tự động đầy đủ.
- Không triển khai theo §0b: MongoDB, Elasticsearch, Postgres, Docker, Streamlit, API demo, streaming simulation, NMF/BERTopic và capture–recapture.

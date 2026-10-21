# Architecture Decisions — Phase 0 đến Phase 4

| Decision | Choice | Reason |
|---|---|---|
| Python | 3.11+ | SPEC requirement |
| Collector contract | `Collector.iter_posts() -> Iterator[RawPost]` | Stable adapter boundary |
| Bronze record | `RawPost` Pydantic model | Explicit contract between stages |
| Primary browser channel | Passive response observation | No manually constructed GraphQL requests |
| DOM fallback | Not implemented in the 48-hour scope if GraphQL works | §0b scope reduction |
| API / streaming demos | Theory-only; no demo code | Explicit §0b exclusion |
| Comments | Disabled | Outside minimal P0 collector scope |
| Synthetic data | Deterministic with seed 42 | Reproducible local tests |
| Checkpoint | Atomic JSON | Small and sufficient for local resume |
| Facebook schema | No schema assumed | Real key paths must be verified against anonymized probe samples |
| Authentication | Manual browser login; local storage state | Passwords are never stored by the application |
| Privacy | HMAC author hash + basic PII scrubbing | Minimize persistent identifiers |
| Storage backends | Not implemented in Phase 0 + 1 | SQLite and Parquet/DuckDB belong to later phase |

## Phase 3–4 — quyết định trong phạm vi rút gọn

| Decision | Choice | Reason |
|---|---|---|
| Corpus đại diện | BoW/TF-IDF fit trên `tokens_nostop` | Giữ cách tokenization từ Silver; lưu sparse `.npz` và vocab JSON có thể tái tạo. |
| E5 | Import lười `sentence-transformers`; model `intfloat/multilingual-e5-small`; prefix `query: `; normalize L2; cache theo doc IDs + nội dung + config | Không để dependency/network/model lỗi chặn BoW và TF-IDF; cảnh báo và ghi trạng thái bỏ qua. |
| Nhãn khi chưa có gán tay | Rule-based weak labels, `proxy_labels=true` ở metrics và từng score | Không trình bày nhãn heuristic như ground truth; macro-F1 nếu dùng proxy chỉ là chỉ số chẩn đoán. |
| Label sample | Phân tầng gần tỷ lệ theo `year_month` và quartile độ dài; seed 42 | Mẫu tái lập được, tránh chỉ lấy bài dài/ngắn hoặc một tháng. Nếu corpus ít, lấy toàn bộ số bài hiện có và cảnh báo. |
| Storage | SQLite stdlib + FTS5 và file Parquet | Ít dependency và khớp yêu cầu rút gọn; Parquet là columnar scan, không giả lập full-text index. |
| Benchmark | 1.000 bootstrap-clone từ Silver, ID riêng, 20 lượt đo | So sánh throughput/latency cục bộ mà không ghi thêm vào database chính; clone được gắn cờ để không nhầm với dữ liệu thật. |
| Bỏ các backend nặng | Không triển khai PostgreSQL, MongoDB, Elasticsearch, DuckDB | Theo yêu cầu Phase 4 rút gọn của Trung; không cài dependency của các backend này. |

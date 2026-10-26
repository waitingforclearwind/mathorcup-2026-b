# 已提交的建库结果快照

`build_master/` 保存 2026-10-26 成功建库后的轻量结果，便于队友直接查看。

- `build_master_report.md`：数据规模、缺测率口径和验证说明。
- `results.json`：本次建库实测结果。
- `build_manifest.json`：原始输入文件及代码配置的摘要。
- `qa_*.csv`：缺测、清洗、QC 和时间轴审计。
- `raw_field_dict.csv`：原始物理量字典。
- `event_day.csv` / `event_window.csv`：事件日和周边窗口切片。

快照对应本次已运行结果；后续重新运行 01 后，需要同步更新快照。
完整主表 `master_hourly.parquet` 位于本地 `data/processed/`，按项目约定不纳入 Git。
队友复现时需取得原始 24 个 CSV，设置 config.py 的路径，再运行 01_build_master.py。
本地 .venv、日志以及原始空间数据同样不纳入 Git。


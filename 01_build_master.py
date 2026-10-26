"""清洗 24 个逐小时 CSV，建立 63 个原始物理量的统一主表。

直接在 PyCharm 运行即可。可选参数见 --help；路径不依赖当前工作目录。
不插值、不填零、不标准化、不生成监督学习标签，也不计算派生特征。
"""
# AI 辅助：OpenAI Codex（GPT-6），OpenAI，2026-10-26。
# 用途：数据管道实现与自动核验；人工采纳和修改情况由参赛者另行记录。
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import logging
import platform
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

try:
    import numpy as np
    import pandas as pd
    import pyarrow  # noqa: F401 - 提前检查 parquet 依赖
except ImportError as exc:
    raise SystemExit(
        "缺少建库依赖，请用项目 .venv 解释器运行，或执行："
        " python -m pip install -r requirements.txt"
    ) from exc

LOG = logging.getLogger("build_master")


def require(condition: bool, message: str) -> None:
    """不用可被 python -O 关闭的 assert 承担生产数据校验。"""
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missing_records(frame: pd.DataFrame, table: str, scope: str,
                    year: int | str) -> list[dict]:
    """缺测率的分母是对应 scope 的小时行数，避免混用全年与截断期。"""
    return [
        {"scope": scope, "table": table, "year": year, "variable": column,
         "n_rows": len(frame), "n_valid": int(frame[column].notna().sum()),
         "n_missing": int(frame[column].isna().sum()),
         "missing_rate": float(frame[column].isna().mean())}
        for column in frame.columns
    ]


def read_clean_file(path: Path, table: str, year: int):
    """严格检查结构，返回清洗表、字段审计、QC 分布和输入清单。"""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream))
    require(len(header) == len(set(header)), f"{path.name}: 重复列名")
    require("Timestamp" in header, f"{path.name}: 缺少 Timestamp")
    # 部分 FLUX 文件使用大写 NAN，pandas 默认缺测词表并不覆盖该拼写。
    raw = pd.read_csv(path, encoding="utf-8-sig", na_values=["NAN", "nan", "NaN"])
    qc_columns = [c for c in header if c.casefold().startswith("qc_")]
    physical = [c for c in header if c != "Timestamp" and c not in qc_columns]
    require((len(physical), len(qc_columns)) == config.TABLES[table],
            f"{path.name}: 物理/QC 列数与约定不符")
    times = pd.to_datetime(raw["Timestamp"], format="mixed", errors="raise")
    require(times.notna().all(), f"{path.name}: 时间为空")
    require(times.dt.tz is None, f"{path.name}: 预期无时区的原始站点时间")
    require(not times.duplicated().any(), f"{path.name}: 重复时间戳，不自动平均")
    require((times.dt.year == year).all(), f"{path.name}: 文件名年份与时间不符")
    require((times == times.dt.floor("h")).all(), f"{path.name}: 存在非整点时间")
    index = pd.DatetimeIndex(times, name="Timestamp")
    values = raw[physical].apply(pd.to_numeric, errors="raise").astype("float64")
    qc_values = raw[qc_columns].apply(pd.to_numeric, errors="raise")
    sentinel = values.abs().ge(config.SENTINEL_ABS_THRESHOLD)
    nonfinite = pd.DataFrame(np.isinf(values.to_numpy()), columns=physical)
    # RADM 中 QC_rsu/QC_rld/QC_rlu 与 Rsu/Rld/Rlu 大小写不一致。
    qc_lookup = {c[3:].casefold(): c for c in qc_columns}
    require(len(qc_lookup) == len(qc_columns), f"{path.name}: QC 名称歧义")
    matched_qc = set()
    qc_mask = pd.DataFrame(False, index=values.index, columns=physical)
    audit, qc_distribution = [], []
    for column in physical:
        qc_column = qc_lookup.get(column.split("(", 1)[0].casefold())
        if qc_column is not None:
            matched_qc.add(qc_column)
            qc_mask[column] = qc_values[qc_column].eq(config.QC_MISSING_FLAG)
        audit.append({
            "file": path.name, "table": table, "year": year,
            "variable": column, "qc_column": qc_column or "",
            "n_raw_missing": int(values[column].isna().sum()),
            "n_sentinel": int(sentinel[column].sum()),
            "n_infinite": int(nonfinite[column].sum()),
            "n_qc8": int(qc_mask[column].sum()),
            "n_qc8_only": int((qc_mask[column] & values[column].notna()
                               & ~sentinel[column]).sum()),
        })
    require(matched_qc == set(qc_columns), f"{path.name}: 存在未对应物理量的 QC 列")
    for column in qc_columns:
        for flag, count in qc_values[column].value_counts(dropna=False).items():
            qc_distribution.append({
                "file": path.name, "qc_column": column,
                "flag": "missing" if pd.isna(flag) else str(flag), "count": int(count),
            })
    cleaned = values.mask(sentinel | nonfinite | qc_mask)
    cleaned.index = index
    cleaned = cleaned.sort_index()
    for record in audit:
        record["n_clean_missing"] = int(cleaned[record["variable"]].isna().sum())
    expected_year = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01",
                                  freq="h", inclusive="left")
    manifest = {
        "file": str(path.resolve()), "table": table, "year": year,
        "sha256": sha256(path), "n_rows": len(raw), "n_columns": len(header),
        "first_timestamp": str(cleaned.index.min()), "last_timestamp": str(cleaned.index.max()),
        "input_was_sorted": bool(index.is_monotonic_increasing),
        "missing_hours_in_calendar_year": len(expected_year.difference(cleaned.index)),
        "physical_columns": physical,
    }
    return cleaned, audit, qc_distribution, manifest


def build_master(input_dir: Path, output_dir: Path) -> dict:
    require(input_dir.is_dir(), f"输入目录不存在：{input_dir}")
    # 防止自定义输出位置落到原始附件中。
    require(not output_dir.is_relative_to(input_dir)
            and not output_dir.is_relative_to(config.ATTACHMENTS_DIR.resolve()),
            "输出目录不能位于原始附件目录内")
    expected_paths = {
        (table, year): input_dir / f"{table}_Gyirong_{year}.csv"
        for table in config.TABLES for year in config.YEARS
    }
    missing = [str(p) for p in expected_paths.values() if not p.is_file()]
    require(not missing, "缺少输入文件：\n" + "\n".join(missing))
    qa, audit, qc_distribution, manifest, dictionary, timeline = [], [], [], [], [], []
    full_tables = {}
    target_index = pd.date_range(config.TIME_START, config.TIME_END, freq="h", name="Timestamp")
    for table in config.TABLES:
        yearly, schema = [], None
        for year in config.YEARS:
            frame, file_audit, file_qc, file_manifest = read_clean_file(
                expected_paths[table, year], table, year)
            if schema is None:
                schema = list(frame.columns)
                for record in file_audit:
                    column = record["variable"]
                    dictionary.append({
                        "table": table, "variable": column,
                        "unit": column.split("(", 1)[1].removesuffix(")") if "(" in column else "",
                        "qc_column": record["qc_column"],
                        "stage": "raw_cleaned", "imputed": False,
                    })
            require(list(frame.columns) == schema, f"{table} {year}: 跨年字段不一致")
            yearly.append(frame)
            qa.extend(missing_records(frame, table, "raw_file", year))
            audit.extend(file_audit)
            qc_distribution.extend(file_qc)
            manifest.append(file_manifest)
        full = pd.concat(yearly).sort_index()
        require(not full.index.duplicated().any(), f"{table}: 跨年重复时间")
        outside = full.loc[~full.index.isin(target_index)]
        require(not outside.notna().any(axis=None),
                f"{table}: 约定时间窗外有有效数值，请核查截止时间，不静默丢弃")
        aligned = full.reindex(target_index)
        timeline.append({
            "table": table, "raw_rows": len(full), "master_rows": len(aligned),
            "padding_rows_removed": len(outside),
            "missing_timestamp_rows_in_master": len(target_index.difference(full.index)),
            "all_physical_missing_rows_in_master": int(aligned.isna().all(axis=1).sum()),
        })
        for year, year_frame in aligned.groupby(aligned.index.year):
            qa.extend(missing_records(year_frame, table, "master_hourly", year))
        qa.extend(missing_records(aligned, table, "master_hourly", "ALL"))
        full_tables[table] = aligned
        LOG.info("%s: 原始 %d 行 -> 对齐 %d 行，保留 %d 个物理量", table, len(full), len(aligned), len(schema))
    master = pd.concat(full_tables.values(), axis=1)
    require(master.columns.is_unique, "四表物理量重名，不能静默改名")
    master = master.reset_index()
    require(master.shape == config.EXPECTED_SHAPE, f"主表尺寸异常：{master.shape}")
    require(pd.DatetimeIndex(master["Timestamp"]).equals(target_index), "主表时间轴不连续或未排序")
    require(not master.iloc[:, 1:].abs().ge(config.SENTINEL_ABS_THRESHOLD).any(axis=None),
            "主表仍含哨兵值")
    require(not np.isinf(master.iloc[:, 1:].to_numpy()).any(), "主表仍含无穷值")
    event_day = master.loc[master["Timestamp"].dt.normalize().eq(pd.Timestamp(config.EVENT_DATE))]
    rain = event_day["Precip(mm)"]
    event_complete = len(rain) == 24 and bool(rain.notna().all())
    event_all_zero = event_complete and bool(rain.eq(0).all())
    require(event_all_zero, "事件日降水并非 24 个完整的零值，请核查输入及交接结论")
    window = master.loc[master["Timestamp"].between(
        pd.Timestamp(config.EVENT_WINDOW_START), pd.Timestamp(config.EVENT_WINDOW_END))].copy()
    rain_after = master.loc[(master["Timestamp"] > pd.Timestamp(config.EVENT_TIME))
                            & master["Precip(mm)"].gt(0), ["Timestamp", "Precip(mm)"]]
    qa_frame = pd.DataFrame(qa)
    precip_qa = qa_frame.loc[qa_frame["variable"].eq("Precip(mm)")].copy()
    results_path = output_dir / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    require(isinstance(results, dict), "results.json 顶层须为对象")
    summary = {
        "status": "completed", "built_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "input_dir": str(input_dir), "output_dir": str(output_dir),
        "rows": len(master), "columns": len(master.columns), "physical_columns": len(master.columns) - 1,
        "time_start": str(master["Timestamp"].min()), "time_end": str(master["Timestamp"].max()),
        "timestamp_policy": "保留 CSV 无时区时间；按交接文件暂作北京时间解读，未作 UTC 转换，原始时区元数据待核实。",
        "cleaning_policy": "abs(value)>=9999 或 QC=8 或非有限值转 NaN；保留其余 QC 对应值；不插补。",
        "event_anchor_from_handover": config.EVENT_TIME,
        "event_time_in_problem": config.PROBLEM_EVENT_TIME,
        "event_day_precip_valid_hours": int(rain.notna().sum()),
        "event_day_precip_mm": float(rain.sum(min_count=24)),
        "event_day_precip_all_zero": event_all_zero,
        "first_positive_precip_after_event": (
            {"timestamp": str(rain_after.iloc[0]["Timestamp"]),
             "precip_mm": float(rain_after.iloc[0]["Precip(mm)"])} if not rain_after.empty else None),
        "event_window_rows": len(window),
        "event_window_start": config.EVENT_WINDOW_START, "event_window_end": config.EVENT_WINDOW_END,
        "precip_missing": precip_qa.to_dict(orient="records"),
        "timeline": timeline,
        "environment": {"python": platform.python_version(),
                        **{name: importlib.metadata.version(name) for name in ("numpy", "pandas", "pyarrow")}},
    }
    results["build_master"] = summary
    provenance = {"inputs": manifest, "code_sha256": sha256(Path(__file__)),
                  "config_sha256": sha256(Path(config.__file__)),
                  "handover_path": str(config.SOURCE_ROOT / "project_state.json"),
                  "contract": {"years": config.YEARS, "time_start": config.TIME_START,
                               "time_end": config.TIME_END, "expected_shape": config.EXPECTED_SHAPE,
                               "sentinel_abs_threshold": config.SENTINEL_ABS_THRESHOLD,
                               "qc_missing_flag": config.QC_MISSING_FLAG}}
    output_dir.mkdir(parents=True, exist_ok=True)
    # 先在临时目录写入并验证，再替换本脚本负责的输出文件。
    with tempfile.TemporaryDirectory(prefix=".build_master_", dir=output_dir) as temp:
        staging = Path(temp)
        master.to_parquet(staging / "master_hourly.parquet", engine="pyarrow", index=False)
        pd.testing.assert_frame_equal(master, pd.read_parquet(staging / "master_hourly.parquet"))
        exports = {
            "qa_missing.csv": qa_frame, "qa_cleaning.csv": pd.DataFrame(audit),
            "qa_qc_flags.csv": pd.DataFrame(qc_distribution), "qa_timeline.csv": pd.DataFrame(timeline),
            "raw_field_dict.csv": pd.DataFrame(dictionary), "event_window.csv": window,
            "event_day.csv": event_day,
        }
        for name, frame in exports.items():
            frame.to_csv(staging / name, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d %H:%M:%S")
        for name, content in {"build_manifest.json": provenance, "results.json": results}.items():
            (staging / name).write_text(json.dumps(content, ensure_ascii=False, indent=2,
                                                  allow_nan=False) + "\n", encoding="utf-8")
        (staging / "build_master_report.md").write_text(make_report(summary), encoding="utf-8")
        for path in sorted(staging.iterdir(), key=lambda p: p.name == "results.json"):
            path.replace(output_dir / path.name)
    LOG.info("验收通过：%d 行 × %d 列；事件日降水 %.1f mm（24/24 小时有效）",
             len(master), len(master.columns), summary["event_day_precip_mm"])
    LOG.info("输出目录：%s", output_dir)
    return summary


def make_report(summary: dict) -> str:
    lines = [
        "# 主表建库运行报告", "", f"生成时间：{summary['built_at']}", "",
        "## 本次结果", "",
        f"主表：{summary['rows']:,} 行 × {summary['columns']} 列（Timestamp + 63 个物理量）。",
        f"时间范围：{summary['time_start']} 至 {summary['time_end']}，逐小时连续。",
        "2026-08-26 的 24 个小时降水全部有效，逐值等于 0 mm。该结论仅描述本站观测。",
        f"事件窗口共 {summary['event_window_rows']} 行，另有 event_day.csv 保留事件日完整 24 小时。", "",
        "## 降水缺测率口径", "",
        "raw_file 以原始 CSV 实际行数为分母；master_hourly 以截止时间内对齐后的小时数为分母。",
        "2026 年全年模板在截止时间后的占位行不进入主表，但计入 raw_file。缺测绝不补零。", "",
        "| 范围 | 年份 | 小时数 | 有效数 | 缺测数 | 缺测率 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["precip_missing"]:
        lines.append(f"| {row['scope']} | {row['year']} | {row['n_rows']} | {row['n_valid']} | "
                     f"{row['n_missing']} | {row['missing_rate']:.6%} |")
    lines.extend([
        "", "## 数据处理与边界", "",
        "- 读取全部 24 个 CSV；QC 列仅参与清洗和审计，不进入 64 列主表。",
        "- 显式识别 FLUX 大写 NAN；abs(value)>=9999、QC=8 和非有限数值转为 NaN；其余 QC 标志分布另存。",
        "- 大小写不敏感匹配 QC；不插值、不标准化、不做特征工程或事件标签。",
        "- 原始时间戳重复、非法时间、非数值、字段漂移、时间窗外存在有效观测时均报错。",
        "- 缺失的小时通过完整时间网格保留为 NaN，并在 qa_timeline.csv 统计；原始文件缺行数在 manifest 中。",
        "- 时间时区尚需原始元数据核实；当前保留 CSV 时间，不做时区换算。",
        "- 事件锚点 10:52:10 来自交接文档，题面 10:30 另存；本脚本未重新验证文献时间。",
        "- 事件窗口含灾后数据，仅用于回顾分析；后续预警训练必须按时间隔离，避免数据泄漏。",
        "", "## 文件用途", "",
        "- master_hourly.parquet：后续特征工程的清洗输入。",
        "- qa_missing.csv：每个物理量按来源表、年份和统计口径的缺测统计。",
        "- qa_cleaning.csv：逐文件逐字段的原始缺测、哨兵值、QC=8 及清洗后缺测计数；原因可能重叠，不能直接相加。",
        "- qa_qc_flags.csv / qa_timeline.csv：QC 分布和时间轴审计。",
        "- raw_field_dict.csv：63 个原始物理量、单位、来源表和 QC 对应列。派生 feature_dict.csv 留给 02 脚本。",
        "- event_window.csv / event_day.csv：事件周边窗口与事件日全天。",
        "- build_manifest.json：24 个输入文件的 SHA256、范围、字段、缺行情况和代码配置摘要。",
        "- results.json：本次实测数值仅写入 build_master 节，保留后续模型结果。",
        "", "## 复现与验收", "",
        "在项目根目录执行 `.venv\\Scripts\\python.exe 01_build_master.py`，或在 PyCharm 选项目 .venv 运行。",
        "已检查尺寸、连续时间轴、唯一列名、哨兵值清除、事件日完整降水及 Parquet 读回一致性。",
        f"环境：{json.dumps(summary['environment'], ensure_ascii=False)}", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=config.HOURLY_DIR,
                        help="包含 24 个逐小时 CSV 的目录")
    parser.add_argument("--output-dir", type=Path, default=config.OUTPUT_DIR,
                        help="输出目录，默认位于脚本目录下 data/processed")
    args = parser.parse_args()
    log_dir = config.PROJECT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(log_dir / "01_build_master.log", encoding="utf-8")])
    try:
        build_master(args.input_dir.resolve(), args.output_dir.resolve())
    except Exception:
        LOG.exception("建库失败；请先解决上述数据或环境问题，再运行。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())


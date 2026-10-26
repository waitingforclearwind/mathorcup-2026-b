# MathorCup 2026 赛道 B 本地代码

已阅读 `project_state.json`、`项目交接文档_v1.md` 和题面，并按当前要求把代码放在本目录。
原始附件仍位于 F 盘 B题目录，代码只读这些文件。交接文件中旧的 `B题/work` 路径由本目录替代。

## 当前进度与方向

交接时已完成数据核查与技术路线设计，未建立持久代码和中间数据。
拟采用“机器学习主干、物理定边界”：Q1 无监督异常分析，Q2 空间易发性与动态触发分开，Q3 区间预报，Q4 物理仿真。
本次仅完成主表建库，其余建模阶段为脚本骨架，未训练模型、未计算 Top5、阈值或覆盖率。
后续实施仍需核验交接材料的方法及物理公式，尤其是单事件条件下的预测标签与验证方式。

## PyCharm 运行

1. 打开本目录，将 Python 解释器设置为：
   `C:\Users\zhong\PyCharmMiscProject\机器学习\啥比赛\mathor cup\.venv\Scripts\python.exe`。
2. 运行 `01_build_master.py`，无需填参数，工作目录任意。
3. 查看 `data/processed/build_master_report.md` 和 `data/processed/results.json`。

项目 `.venv` 已创建并安装建库依赖；实际解释器为 Python 3.13.14。
在项目目录的 PowerShell 也可以执行：

```powershell
& '.\.venv\Scripts\python.exe' '.\01_build_master.py'
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

迁移到其他机器时：创建 `.venv`，执行 `python -m pip install -r requirements-lock.txt`，
修改 `config.py` 的 `SOURCE_ROOT`，或通过 `--input-dir` 指定包含 24 个 CSV 的目录。
输出目录可用 `--output-dir` 覆盖。脚本重复运行会更新其生成的数据和报告；
`results.json` 只更新 `build_master` 节，保留其他阶段的记录。

## 脚本清单

交接文件未规定后续脚本命名，以下按流水线阶段划分。

| 文件 | 职责 | 状态 |
|---|---|---|
| config.py | 统一路径、时间范围、字段数量与清洗约定 | 可用 |
| 01_build_master.py | 24 个 CSV 清洗、对齐、合并和审计 | 已实现并跑通 |
| 02_build_features.py | 时序特征及派生特征字典 | 骨架 |
| 03_q1_analysis.py | Q1 异常归因、事件合成及 Top5 | 骨架 |
| 04_prepare_spatial.py | 空间数据、地形因子与背景样本 | 骨架 |
| 05_q2_susceptibility.py | Q2 空间易发性及空间验证 | 骨架 |
| 06_q2_trigger.py | Q2 临界条件与动态触发指标 | 骨架 |
| 07_q3_forecast.py | Q3 区间、预警提前量及验证 | 骨架 |
| 08_q4_simulation.py | Q4 仿真与过程输出 | 骨架 |
| 09_q4_sensitivity.py | Q4 情景、代理及敏感性分析 | 骨架 |
| 10_collect_results.py | 结果汇总和交付验收 | 骨架 |

骨架含输入、输出、约束及 `main()`，运行会明确抛出 `NotImplementedError`。

## 已生成的结果

全部数据和报告位于 `data/processed/`：

- `master_hourly.parquet`：49,545 行 × 64 列，原始 Timestamp + 63 个物理量，单位保留在列名中。
- `qa_missing.csv`：原始 CSV 年度口径和主表有效时间范围口径的缺测率。
- `event_window.csv`：2026-08-23 00:00 至 08-27 08:00，共 105 行。
- `event_day.csv`：2026-08-26 全天 24 行，降水逐值为 0 mm。
- `qa_cleaning.csv`、`qa_qc_flags.csv`、`qa_timeline.csv`：清洗计数、QC 标志分布和时间轴质量。
- `raw_field_dict.csv`：63 个原始字段的来源、单位、QC 对应列；派生特征字典由 02 阶段负责。
- `build_manifest.json`：输入文件 SHA256、字段、范围、代码及配置摘要。
- `results.json`、`build_master_report.md`：实测结果与口径说明。

日志位于 `logs/01_build_master.log`。

## 已核实的数据差异

- FLUX 含大写字符串 `NAN`，已显式识别。
- RADM 的部分 QC 名称大小写与物理列不同，已正确对应。
- QC 实际含 0、1、2、4、8、9；按交接约定只对 QC=8 额外掩码，其他标志保留并审计，其含义后续需查源数据说明。
- 2026 全年 CSV 降水缺测率为 34.703196%；截断到 08-27 08:00 后仅 1/5721 小时缺测，即 0.017479%。
- 2022–2025 年降水也有每年 1–2 小时缺测，交接中的“0.0%”是舍入结果。
- 原始每表共有 52,584 行，截止时间后 3,039 行均无有效物理值，已剔除；有效区间内缺测行保留。

不插值、不填零、不标准化。`event_window.csv` 包含灾后数据，仅适用于回顾分析；后续预警建模需自行隔离。
CSV 时区元数据尚未核验，本阶段保持原始时间，不擅自进行 UTC/北京时间换算。
10:52:10 使用交接文档的事件锚点，题面 10:30 另行记录；本阶段未重新核查该文献时间。


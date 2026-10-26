"""MathorCup B 题共享路径与建库约定。原始数据仅以只读方式访问。"""
# AI 辅助：OpenAI Codex（GPT-6），OpenAI，2026-10-26；需由参赛者复核。
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = Path(r"F:\desktop\一堆文件\big school\大二\上学期\啥比赛\mathorcup\B题")
ATTACHMENTS_DIR = SOURCE_ROOT / "2026年MathorCup大数据挑战赛-赛道B初赛" / "附件"
HOURLY_DIR = ATTACHMENTS_DIR / "（1）西藏吉隆高寒山区地气相互作用逐小时综合观测数据集（2021–2026）"
OUTPUT_DIR = PROJECT_DIR / "data" / "processed"
YEARS = tuple(range(2021, 2027))
# 顺序也定义主表的列顺序。每项为：物理列数、QC 列数。
TABLES = {"MET": (22, 21), "SOIL": (12, 12), "RADM": (4, 4), "FLUX": (25, 0)}
TIME_START = "2021-01-01 00:00:00"
TIME_END = "2026-08-27 08:00:00"
EXPECTED_SHAPE = (49545, 64)
SENTINEL_ABS_THRESHOLD = 9999
QC_MISSING_FLAG = 8
EVENT_DATE = "2026-08-26"
# 采用交接文档的事件锚点；题面时间 10:30 另外保留，不宣称本脚本核验了文献。
EVENT_TIME = "2026-08-26 10:52:10"
PROBLEM_EVENT_TIME = "2026-08-26 10:30:00"
# 覆盖事件前 72 小时合成分析区间、事件日全天及全部已观测灾后时段。
EVENT_WINDOW_START = "2026-08-23 00:00:00"
EVENT_WINDOW_END = TIME_END


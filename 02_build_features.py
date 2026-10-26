"""待实现：时序特征工程。

输入：data/processed/master_hourly.parquet。
输出规划：features_hourly.parquet、feature_dict.csv。
任务：温度梯度、风切变、净辐射、土壤剖面、API、正积温等。
约束：窗口只使用当前及过去数据；缺测降水不能补零；单位与源区订正须核实。
"""
# AI 辅助：OpenAI Codex（GPT-6），OpenAI，2026-10-26；当前仅为骨架。
import config


def main() -> None:
    raise NotImplementedError("02 尚未实现：请以 config.OUTPUT_DIR 下的主表进行特征工程。")


if __name__ == "__main__":
    main()


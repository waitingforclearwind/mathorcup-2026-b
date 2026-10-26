"""待实现：Q1 异常分析与 Top5。

输入：features_hourly.parquet、feature_dict.csv。
输出规划：异常分数、消融排序、事件合成分析、Top5 与图表。
路线：AutoEncoder 主模型 + Isolation Forest 基线，三证据与稳定性检验。
约束：训练 2021–2025，验证不含 2026-08-26；预处理仅在训练集拟合。
"""
# AI 辅助：OpenAI Codex（GPT-6），OpenAI，2026-10-26；当前仅为骨架。
import config


def main() -> None:
    raise NotImplementedError("03 尚未实现：先完成 02 特征库，再开展 Q1。")


if __name__ == "__main__":
    main()


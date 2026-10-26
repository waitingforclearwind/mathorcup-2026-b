"""覆盖实际数据管道中容易静默损坏观测值的边界情形。"""
# AI 辅助：OpenAI Codex（GPT-6），OpenAI，2026-10-26。
import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("build_master", ROOT / "01_build_master.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CleaningRegressionTests(unittest.TestCase):
    def read_radiation(self, rows):
        header = ["Timestamp", "Rsd(W/m2)", "QC_Rsd", "Rsu(W/m2)", "QC_rsu",
                  "Rld(W/m2)", "QC_rld", "Rlu(W/m2)", "QC_rlu"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "RADM_Gyirong_2026.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(header)
                writer.writerows(rows)
            return module.read_clean_file(path, "RADM", 2026)[0]

    def test_qc_case_and_signed_sentinel_without_zero_imputation(self):
        frame = self.read_radiation([
            ["2026-1-1 0:00", -5, 0, 12, 8, 9999.9, 0, -9999.9, 0],
            ["2026/1/1 1:00", 0, 0, 2, 1, 3, 2, 4, 9],
        ])
        self.assertEqual(frame.iloc[0, 0], -5)
        self.assertTrue(frame.iloc[0, 1:].isna().all())
        self.assertEqual(frame.iloc[1].tolist(), [0, 2, 3, 4])

    def test_uppercase_nan_in_flux(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "FLUX_Gyirong_2026.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Timestamp"] + [f"flux_{i}" for i in range(25)])
                writer.writerow(["2026/1/1 0:00", "NAN", "NaN", ""] + [0] * 22)
            frame = module.read_clean_file(path, "FLUX", 2026)[0]
            self.assertTrue(frame.iloc[0, :3].isna().all())
            self.assertTrue(frame.iloc[0, 3:].eq(0).all())

    def test_duplicate_timestamp_is_rejected(self):
        row = ["2026-1-1 0:00", 1, 0, 2, 0, 3, 0, 4, 0]
        with self.assertRaisesRegex(ValueError, "重复时间戳"):
            self.read_radiation([row, row])

    def test_invalid_numeric_value_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            self.read_radiation([["2026-1-1 0:00", "broken", 0, 2, 0, 3, 0, 4, 0]])

    def test_non_hourly_and_wrong_year_are_rejected(self):
        for timestamp in ["2026-1-1 0:30", "2025-1-1 0:00"]:
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.read_radiation([[timestamp, 1, 0, 2, 0, 3, 0, 4, 0]])


if __name__ == "__main__":
    unittest.main()


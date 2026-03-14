import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from heap_seance_mcp.heuristics import (
    gc_pressure_signal,
    monotonic_growth_candidates,
    overall_confidence,
)


class HeuristicsTests(unittest.TestCase):
    def test_monotonic_growth_candidates(self) -> None:
        histograms = [
            {
                "top_classes": [
                    {"class_name": "com.example.Leak", "bytes": 1_000_000},
                    {"class_name": "com.example.Other", "bytes": 100_000},
                ]
            },
            {
                "top_classes": [
                    {"class_name": "com.example.Leak", "bytes": 2_000_000},
                    {"class_name": "com.example.Other", "bytes": 90_000},
                ]
            },
            {
                "top_classes": [
                    {"class_name": "com.example.Leak", "bytes": 3_200_000},
                    {"class_name": "com.example.Other", "bytes": 88_000},
                ]
            },
        ]

        candidates = monotonic_growth_candidates(histograms)
        self.assertEqual(1, len(candidates))
        self.assertEqual("com.example.Leak", candidates[0]["class_name"])

    def test_gc_pressure_signal(self) -> None:
        signal = gc_pressure_signal(
            {
                "max_oldgen_utilization": 85,
                "full_gc_delta": 2,
                "oldgen_slope": 4,
            }
        )
        self.assertTrue(signal["pressure_detected"])

    def test_overall_confidence(self) -> None:
        assessment = overall_confidence(
            monotonic_candidates=[{"class_name": "com.example.Leak"}],
            gc_pressure={"pressure_detected": True},
            mat_holder={"holder_detected": True},
            jfr_support={"supports_histogram_candidates": True},
        )
        self.assertEqual("high", assessment["confidence"])
        self.assertEqual("probable_memory_leak", assessment["verdict"])


if __name__ == "__main__":
    unittest.main()

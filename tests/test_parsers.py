import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from heap_seance_mcp.parsers import (
    parse_heap_histogram,
    parse_jcmd_processes,
    parse_jfr_summary,
    parse_jstat_gcutil,
)


class ParserTests(unittest.TestCase):
    def test_parse_jcmd_processes(self) -> None:
        raw = """\
1234 com.example.Main --spring.profiles.active=dev
9999 jdk.jcmd/sun.tools.jcmd.JCmd -l
"""
        parsed = parse_jcmd_processes(raw)
        self.assertEqual(2, len(parsed))
        self.assertEqual(1234, parsed[0]["pid"])
        self.assertIn("com.example.Main", parsed[0]["main_class"])

    def test_parse_jstat_gcutil(self) -> None:
        raw = """\
  S0     S1     E      O      M     CCS    YGC   YGCT   FGC    FGCT     GCT
  0.00   0.00  11.12  65.00  80.12 71.12    10   0.123     1    0.500    0.623
  0.00   0.00  22.11  82.00  80.12 71.12    11   0.140     2    0.710    0.850
"""
        parsed = parse_jstat_gcutil(raw)
        self.assertEqual(2, parsed["summary"]["sample_count"])
        self.assertAlmostEqual(82.0, parsed["summary"]["max_oldgen_utilization"])
        self.assertAlmostEqual(1.0, parsed["summary"]["full_gc_delta"])

    def test_parse_jstat_gcutil_comma_locale(self) -> None:
        raw = """\
  S0     S1     E      O      M     CCS    YGC   YGCT   FGC    FGCT     GCT
  0,00   0,00  11,12  65,00  80,12 71,12    10   0,123     1    0,500    0,623
  0,00   0,00  22,11  82,00  80,12 71,12    11   0,140     2    0,710    0,850
"""
        parsed = parse_jstat_gcutil(raw)
        self.assertEqual(2, parsed["summary"]["sample_count"])
        self.assertAlmostEqual(82.0, parsed["summary"]["max_oldgen_utilization"])
        self.assertAlmostEqual(1.0, parsed["summary"]["full_gc_delta"])

    def test_parse_heap_histogram(self) -> None:
        raw = """\
 num     #instances         #bytes  class name (module)
-------------------------------------------------------
   1:          10          40960  com.example.Foo
   2:           5          10240  [B (java.base@17)
Total          15          51200
"""
        parsed = parse_heap_histogram(raw)
        self.assertEqual(2, parsed["summary"]["entry_count"])
        self.assertEqual(51200, parsed["summary"]["total_bytes"])
        self.assertEqual("com.example.Foo", parsed["top_classes"][0]["class_name"])

    def test_parse_jfr_summary(self) -> None:
        raw = """\
 Version: 2.0
 jdk.ObjectCountAfterGC 12 3456
 jdk.ObjectAllocationSample 99 2000
"""
        parsed = parse_jfr_summary(raw)
        self.assertTrue(parsed["contains_object_count_after_gc"])
        self.assertEqual(2, len(parsed["event_counts"]))


if __name__ == "__main__":
    unittest.main()

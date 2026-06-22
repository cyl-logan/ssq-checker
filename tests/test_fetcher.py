"""Tests for fetcher: parse data format, no network calls."""
from ssq_checker.fetcher import parse_line


def test_parse_real_line():
    """Real line copied from 17500.cn."""
    line = "2026070 2026-06-21 03 06 08 14 26 27 08 14 03 26 08 06 27 398555946 438183968 11 5811271 216 165258 2030 3000 98536 200 1700584 10 11007971 5 10565919 5"
    d = parse_line(line)
    assert d.issue == "2026070"
    assert d.date == "2026-06-21"
    assert d.reds == ["03", "06", "08", "14", "26", "27"]
    assert d.blue == "08"


def test_reds_sorted():
    line = "2026070 2026-06-21 27 06 26 14 03 08 08"
    d = parse_line(line)
    assert d.reds_sorted == ["03", "06", "08", "14", "26", "27"]


def test_strips_whitespace():
    line = "   2026070 2026-06-21 03 06 08 14 26 27 08   \n"
    d = parse_line(line)
    assert d.issue == "2026070"

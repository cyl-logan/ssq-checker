"""Tests for red/blue distribution stats (no network)."""
import json

from ssq_checker.fetcher import Draw
from ssq_checker.stats import compute_stats, write_stats


def _draw(issue, date, reds, blue):
    return Draw(issue=issue, date=date, reds=reds, blue=blue)


def _by_num(items):
    return {d["num"]: d for d in items}


def test_compute_counts_and_span():
    draws = [
        _draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07"),
        _draw("2025002", "2025-01-04", ["01", "02", "10", "11", "12", "13"], "07"),
    ]
    s = compute_stats(draws)
    assert s["total_draws"] == 2
    assert s["span"] == {
        "first_date": "2025-01-02", "last_date": "2025-01-04",
        "first_issue": "2025001", "last_issue": "2025002",
    }
    reds = _by_num(s["reds"])
    assert len(s["reds"]) == 33 and len(s["blue"]) == 16
    assert reds["01"]["count"] == 2   # in both draws
    assert reds["03"]["count"] == 1   # only first
    assert reds["33"]["count"] == 0   # never
    blue = _by_num(s["blue"])
    assert blue["07"]["count"] == 2 and blue["01"]["count"] == 0


def test_gap_and_max_gap():
    # 01 appears in draw1, absent in 2 and 3 -> current gap 2.
    draws = [
        _draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07"),
        _draw("2025002", "2025-01-04", ["10", "11", "12", "13", "14", "15"], "08"),
        _draw("2025003", "2025-01-06", ["10", "11", "12", "13", "14", "15"], "09"),
    ]
    reds = _by_num(compute_stats(draws)["reds"])
    assert reds["01"]["gap"] == 2 and reds["01"]["max_gap"] == 2
    # 10 first appears at draw2 (leading gap 1), present in 2 and 3 -> current gap 0.
    assert reds["10"]["gap"] == 0 and reds["10"]["max_gap"] == 1
    # 33 never appears -> gap == max_gap == total draws.
    assert reds["33"]["gap"] == 3 and reds["33"]["max_gap"] == 3


def test_avg_gap():
    # 01 appears once across 3 draws -> avg omission = (3-1)/(1+1) = 1.0
    # 10 appears in 2 of 3 draws -> avg omission = (3-2)/(2+1) = 0.3
    draws = [
        _draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07"),
        _draw("2025002", "2025-01-04", ["10", "11", "12", "13", "14", "15"], "08"),
        _draw("2025003", "2025-01-06", ["10", "11", "12", "13", "14", "15"], "09"),
    ]
    reds = _by_num(compute_stats(draws)["reds"])
    assert reds["01"]["avg_gap"] == 1.0
    assert reds["10"]["avg_gap"] == 0.3


def test_ordering_independent():
    a = _draw("2025002", "2025-01-04", ["10", "11", "12", "13", "14", "15"], "08")
    b = _draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07")
    # Pass out of order; compute_stats sorts by (date, issue), so 01's gap is 1.
    reds = _by_num(compute_stats([a, b])["reds"])
    assert reds["01"]["gap"] == 1


def test_empty():
    s = compute_stats([])
    assert s["total_draws"] == 0 and s["span"] == {}
    assert _by_num(s["reds"])["01"]["count"] == 0


def test_write_and_preserve_generated_at(tmp_path):
    draws = [_draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07")]
    write_stats(str(tmp_path), draws, generated_at="2025-01-01T00:00:00")
    assert (tmp_path / "stats.json").exists()
    # Same data, different timestamp -> preserved (diff-clean).
    m2 = write_stats(str(tmp_path), draws, generated_at="2026-09-09T09:09:09")
    assert m2["generated_at"] == "2025-01-01T00:00:00"
    with open(tmp_path / "stats.json", encoding="utf-8") as f:
        assert json.load(f)["generated_at"] == "2025-01-01T00:00:00"


def test_write_updates_on_new_draw(tmp_path):
    d1 = _draw("2025001", "2025-01-02", ["01", "02", "03", "04", "05", "06"], "07")
    write_stats(str(tmp_path), [d1], generated_at="2025-01-01T00:00:00")
    d2 = _draw("2025002", "2025-01-04", ["10", "11", "12", "13", "14", "15"], "08")
    m = write_stats(str(tmp_path), [d1, d2], generated_at="2026-09-09T09:09:09")
    assert m["generated_at"] == "2026-09-09T09:09:09"
    assert m["total_draws"] == 2

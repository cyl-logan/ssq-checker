"""Tests for month-partitioned history sync and full-feed parsing (no network)."""
import json

from ssq_checker.bets import parse_bets
from ssq_checker.fetcher import Draw, parse_all
from ssq_checker.history import build_record, month_of, sync_history

BETS_5X = parse_bets("红球,蓝球,倍数\n01 02 03 04 08 09,07,5\n")   # cost 10/draw
BETS_1X = parse_bets("红球,蓝球,倍数\n11 12 13 14 15 16,01,1\n")   # cost 2/draw


def _draw(issue, date, reds, blue):
    return Draw(issue=issue, date=date, reds=reds, blue=blue)


def _read(data_dir, name):
    with open(data_dir / name, encoding="utf-8") as f:
        return json.load(f)


def test_parse_all_skips_short_lines():
    text = (
        "2026069 2025-12-30 01 02 03 04 08 09 07 sales pool\n"
        "\n"
        "short line\n"
        "2026070 2026-06-21 11 12 13 14 15 16 08 x y\n"
    )
    assert [d.issue for d in parse_all(text)] == ["2026069", "2026070"]


def test_month_of():
    assert month_of("2025-01-02") == "2025-01"


def test_build_record_fixed_prize_with_multiplier():
    # 3 reds + blue -> 五等奖 ¥10 x5 = 50
    rec = build_record(_draw("2025001", "2025-01-02", ["01", "02", "03", "20", "25", "30"], "07"), BETS_5X)
    assert rec["won"] == 50 and rec["cost"] == 10 and rec["net"] == 40
    assert rec["best_tier"] == "五等奖" and rec["pool_win"] is False
    assert rec["bets"] == [{"reds": ["01", "02", "03", "04", "08", "09"], "blue": "07", "multiplier": 5}]


def test_sync_filters_by_start_date(tmp_path):
    draws = [
        _draw("2024999", "2024-12-31", ["11", "12", "13", "14", "15", "16"], "08"),  # excluded
        _draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08"),
    ]
    m = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    assert m["summary"]["draws"] == 1
    assert m["added"] == 1
    assert m["months"] == ["2025-01"]


def test_sync_partitions_by_month(tmp_path):
    draws = [
        _draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08"),
        _draw("2025010", "2025-02-04", ["11", "12", "13", "14", "15", "16"], "08"),
    ]
    sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    assert (tmp_path / "2025-01.json").exists()
    assert (tmp_path / "2025-02.json").exists()
    assert _read(tmp_path, "2025-01.json")["draws"][0]["issue"] == "2025001"


def test_sync_is_incremental_and_freezes_past(tmp_path):
    d1 = _draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08")
    # First sync with 5x bets.
    sync_history(str(tmp_path), [d1], BETS_5X, "2025-01-01")
    rec1 = _read(tmp_path, "2025-01.json")["draws"][0]
    assert rec1["cost"] == 10

    # Second sync: bets changed to a different set, and a new draw appears.
    d2 = _draw("2025002", "2025-01-04", ["11", "12", "13", "14", "15", "16"], "08")
    m = sync_history(str(tmp_path), [d1, d2], BETS_1X, "2025-01-01")
    recs = _read(tmp_path, "2025-01.json")["draws"]
    assert m["added"] == 1  # only the new draw
    # Old record keeps its original 5x snapshot, untouched.
    assert recs[0]["issue"] == "2025001" and recs[0]["cost"] == 10
    assert recs[0]["bets"][0]["multiplier"] == 5
    # New record uses the current 1x bets.
    assert recs[1]["issue"] == "2025002" and recs[1]["cost"] == 2
    assert recs[1]["bets"][0]["multiplier"] == 1


def test_sync_idempotent(tmp_path):
    draws = [_draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08")]
    sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    m = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    assert m["added"] == 0
    assert m["summary"]["draws"] == 1


def test_manifest_summary_and_latest(tmp_path):
    draws = [
        _draw("2025001", "2025-01-02", ["01", "02", "03", "20", "25", "30"], "07"),  # 五等奖 ¥50
        _draw("2025002", "2025-01-04", ["11", "12", "13", "14", "15", "16"], "08"),  # no prize
    ]
    m = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    assert m["summary"] == {
        "draws": 2, "total_cost": 20, "total_won": 50, "net": 30, "pool_wins": 0,
    }
    assert m["latest"]["issue"] == "2025002"
    idx = _read(tmp_path, "index.json")
    assert idx["months"] == ["2025-01"]


def test_sync_preserves_generated_at_when_unchanged(tmp_path):
    draws = [_draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08")]
    m1 = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01",
                      generated_at="2025-01-01T00:00:00")
    # Second sync with a different `generated_at` — nothing else changed, so the
    # manifest's timestamp should be preserved (no spurious commit).
    m2 = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01",
                      generated_at="2026-09-09T09:09:09")
    assert m2["added"] == 0
    assert m2["generated_at"] == "2025-01-01T00:00:00"
    on_disk = _read(tmp_path, "index.json")
    assert on_disk["generated_at"] == "2025-01-01T00:00:00"


def test_sync_updates_generated_at_when_new_draw(tmp_path):
    d1 = _draw("2025001", "2025-01-02", ["11", "12", "13", "14", "15", "16"], "08")
    sync_history(str(tmp_path), [d1], BETS_5X, "2025-01-01",
                 generated_at="2025-01-01T00:00:00")
    d2 = _draw("2025002", "2025-01-04", ["11", "12", "13", "14", "15", "16"], "08")
    m = sync_history(str(tmp_path), [d1, d2], BETS_5X, "2025-01-01",
                     generated_at="2026-09-09T09:09:09")
    assert m["added"] == 1
    assert m["generated_at"] == "2026-09-09T09:09:09"


def test_pool_win_flagged_not_counted(tmp_path):
    draws = [_draw("2025001", "2025-01-02", ["01", "02", "03", "04", "08", "09"], "07")]  # 一等奖
    m = sync_history(str(tmp_path), draws, BETS_5X, "2025-01-01")
    assert m["summary"]["pool_wins"] == 1
    assert m["summary"]["total_won"] == 0
    rec = _read(tmp_path, "2025-01.json")["draws"][0]
    assert rec["pool_win"] is True and rec["best_tier"] == "一等奖"

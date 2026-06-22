"""Tests for prize-checking logic, using Logan's fixed numbers (red 01 02 03 04 08 09, blue 07)."""
from ssq_checker.checker import check_prize, format_report, normalize
from ssq_checker.fetcher import Draw

USER_REDS = ["01", "02", "03", "04", "08", "09"]
USER_BLUE = "07"


def _draw(reds: list[str], blue: str) -> Draw:
    return Draw(issue="2026099", date="2026-01-01", reds=reds, blue=blue)


def test_normalize_zero_pads():
    assert normalize([1, 2, "3", "08", 9]) == ["01", "02", "03", "08", "09"]


def test_no_prize():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["11", "12", "13", "14", "15", "16"], "08"))
    assert r.tier is None
    assert r.amount is None
    assert r.red_hits == 0
    assert r.blue_hit is False


def test_only_blue_match_wins_6th():
    # 0 reds + blue -> 六等奖 ¥5
    r = check_prize(USER_REDS, USER_BLUE, _draw(["11", "12", "13", "14", "15", "16"], "07"))
    assert r.tier == "六等奖"
    assert r.amount == 5
    assert r.blue_hit is True


def test_2_reds_plus_blue_wins_6th():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "13", "14", "15", "16"], "07"))
    assert r.tier == "六等奖"
    assert r.red_hits == 2
    assert r.red_matched == ["01", "02"]


def test_3_reds_plus_blue_wins_5th():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "03", "14", "15", "16"], "07"))
    assert r.tier == "五等奖"
    assert r.amount == 10


def test_4_reds_no_blue_wins_5th():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "03", "04", "15", "16"], "08"))
    assert r.tier == "五等奖"
    assert r.amount == 10


def test_4_reds_plus_blue_wins_4th():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "03", "04", "15", "16"], "07"))
    assert r.tier == "四等奖"
    assert r.amount == 200


def test_5_reds_no_blue_wins_4th():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "03", "04", "08", "16"], "11"))
    assert r.tier == "四等奖"
    assert r.amount == 200


def test_5_reds_plus_blue_wins_3rd():
    r = check_prize(USER_REDS, USER_BLUE, _draw(["01", "02", "03", "04", "08", "16"], "07"))
    assert r.tier == "三等奖"
    assert r.amount == 3000


def test_6_reds_no_blue_wins_2nd_pool_based():
    r = check_prize(USER_REDS, USER_BLUE, _draw(USER_REDS, "11"))
    assert r.tier == "二等奖"
    assert r.amount is None  # pool-based


def test_6_reds_plus_blue_jackpot():
    r = check_prize(USER_REDS, USER_BLUE, _draw(USER_REDS, "07"))
    assert r.tier == "一等奖"
    assert r.amount is None  # pool-based


def test_report_format_contains_key_fields():
    draw = _draw(["01", "02", "03", "20", "25", "30"], "07")
    r = check_prize(USER_REDS, USER_BLUE, draw)
    msg = format_report(draw, USER_REDS, USER_BLUE, r)
    assert "🎱 双色球第2026099期" in msg
    assert "你的号码：🔴 01 02 03 04 08 09  🔵 07" in msg
    assert "红球命中：3个" in msg
    assert "（01 02 03）" in msg
    assert "蓝球命中：✅" in msg
    assert "🎉 五等奖" in msg


def test_report_no_prize_message():
    draw = _draw(["11", "12", "13", "14", "15", "16"], "08")
    r = check_prize(USER_REDS, USER_BLUE, draw)
    assert "未中奖" in format_report(draw, USER_REDS, USER_BLUE, r)

"""Tests for bet-table parsing and multiplier winnings."""
import pytest

from ssq_checker.bets import Bet, load_bets, parse_bets
from ssq_checker.checker import bet_winnings, check_prize, format_bets_report
from ssq_checker.fetcher import Draw


def _draw(reds, blue):
    return Draw(issue="2026099", date="2026-01-01", reds=reds, blue=blue)


def test_parse_basic_row():
    bets = parse_bets("红球,蓝球,倍数\n01 02 03 04 08 09,07,2\n")
    assert bets == [Bet(reds=["01", "02", "03", "04", "08", "09"], blue="07", multiplier=2)]
    assert bets[0].cost == 4  # 2 RMB * 2


def test_blank_multiplier_defaults_to_1():
    bets = parse_bets("红球,蓝球,倍数\n01 02 03 04 08 09,07,\n")
    assert bets[0].multiplier == 1
    assert bets[0].cost == 2


def test_skips_comments_and_blank_lines():
    text = "# header comment\n红球,蓝球,倍数\n\n01 02 03 04 08 09,07,1\n# trailing\n"
    assert len(parse_bets(text)) == 1


def test_english_headers_accepted():
    bets = parse_bets("reds,blue,multiplier\n05 12 18 22 27 33,11,3\n")
    assert bets[0].blue == "11"
    assert bets[0].multiplier == 3


def test_multiple_rows():
    text = "红球,蓝球,倍数\n01 02 03 04 08 09,07,1\n05 12 18 22 27 33,11,2\n"
    bets = parse_bets(text)
    assert len(bets) == 2
    assert sum(b.cost for b in bets) == 2 + 4


@pytest.mark.parametrize("bad,msg", [
    ("红球,蓝球,倍数\n01 02 03 04 08,07,1\n", "红球应为6个"),
    ("红球,蓝球,倍数\n01 02 03 04 08 08,07,1\n", "重复"),
    ("红球,蓝球,倍数\n01 02 03 04 08 34,07,1\n", "超出 1-33"),
    ("红球,蓝球,倍数\n01 02 03 04 08 09,17,1\n", "超出 1-16"),
    ("红球,蓝球,倍数\n01 02 03 04 08 09,07,0\n", "倍数必须"),
    ("红球,蓝球,倍数\n01 02 03 04 08 09,07,abc\n", "倍数无法解析"),
])
def test_invalid_rows_raise(bad, msg):
    with pytest.raises(ValueError) as e:
        parse_bets(bad)
    assert msg in str(e.value)
    assert "第2行" in str(e.value)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        parse_bets("红球,倍数\n01 02 03 04 08 09,1\n")


def test_load_bets_from_file(tmp_path):
    f = tmp_path / "bets.csv"
    f.write_text("红球,蓝球,倍数\n01 02 03 04 08 09,07,2\n", encoding="utf-8")
    bets = load_bets(str(f))
    assert bets[0].multiplier == 2


def test_load_bets_strips_utf8_bom(tmp_path):
    f = tmp_path / "bets.csv"
    f.write_bytes("\ufeff红球,蓝球,倍数\n01 02 03 04 08 09,07,1\n".encode("utf-8"))
    assert load_bets(str(f))[0].blue == "07"


def test_bet_winnings_multiplies_fixed_amount():
    # 3 reds + blue -> 五等奖 ¥10, x3 -> 30
    draw = _draw(["01", "02", "03", "14", "15", "16"], "07")
    r = check_prize(["01", "02", "03", "04", "08", "09"], "07", draw)
    assert bet_winnings(r, 3) == 30


def test_bet_winnings_zero_for_no_prize():
    draw = _draw(["11", "12", "13", "14", "15", "16"], "08")
    r = check_prize(["01", "02", "03", "04", "08", "09"], "07", draw)
    assert bet_winnings(r, 5) == 0


def test_bet_winnings_none_for_pool_based():
    # 6 reds + blue -> 一等奖, pool-based
    user = ["01", "02", "03", "04", "08", "09"]
    r = check_prize(user, "07", _draw(user, "07"))
    assert bet_winnings(r, 2) is None


def test_format_bets_report_totals():
    draw = _draw(["01", "02", "03", "14", "15", "16"], "07")
    bets = parse_bets(
        "红球,蓝球,倍数\n"
        "01 02 03 04 08 09,07,2\n"   # 3 reds + blue -> 五等奖 ¥10 x2 = 20
        "11 12 13 22 27 33,05,1\n"   # no prize
    )
    results = [(b, check_prize(b.reds, b.blue, draw)) for b in bets]
    msg = format_bets_report(draw, results)
    assert "共2注" in msg
    assert "总投入 ¥6" in msg          # 4 + 2
    assert "总中奖：¥20" in msg
    assert "未中奖" in msg
    assert "🎉 五等奖" in msg

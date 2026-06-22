"""Tests for CLI mode selection (no network)."""
import unittest.mock as m

import pytest

from ssq_checker import __main__ as cli
from ssq_checker.fetcher import Draw


def test_explicit_missing_bets_exits_4_without_fetch(tmp_path, capsys):
    bad = tmp_path / "does-not-exist.csv"
    # fetch_latest_draw must NOT be called when --bets is missing.
    with m.patch.object(cli, "fetch_latest_draw", side_effect=AssertionError("must not fetch")):
        rc = cli.main(["--bets", str(bad)])
    assert rc == 4
    assert "投注表不存在" in capsys.readouterr().err


def test_explicit_bets_used_when_present(tmp_path):
    f = tmp_path / "b.csv"
    f.write_text("红球,蓝球,倍数\n01 02 03 04 08 09,07,5\n", encoding="utf-8")
    draw = Draw(issue="2026070", date="2026-06-21",
                reds=["11", "12", "13", "14", "15", "16"], blue="08")
    with m.patch.object(cli, "fetch_latest_draw", return_value=draw):
        rc = cli.main(["--bets", str(f)])
    assert rc == 0


def test_blue_without_reds_is_rejected(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--blue", "11"])
    assert e.value.code == 2  # argparse error
    assert "--blue requires --reds" in capsys.readouterr().err


def test_reds_flag_overrides_table(tmp_path):
    # When --reds is given explicitly, the table is ignored even if bets.csv exists.
    f = tmp_path / "b.csv"
    f.write_text("红球,蓝球,倍数\n01 02 03 04 08 09,07,5\n", encoding="utf-8")
    draw = Draw(issue="2026070", date="2026-06-21",
                reds=["11", "12", "13", "14", "15", "16"], blue="08")
    with m.patch.object(cli, "fetch_latest_draw", return_value=draw):
        rc = cli.main(["--bets", str(f), "--reds", "01", "02", "03", "04", "05", "06", "--blue", "07"])
    assert rc == 0

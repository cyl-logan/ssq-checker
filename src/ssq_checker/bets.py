"""Load the user's bet table from CSV.

CSV columns (header row required, Chinese or English accepted):
    红球,蓝球,倍数
    01 02 03 04 08 09,07,1

- 红球: 6 distinct numbers 1-33, space-separated, in one cell.
- 蓝球: 1 number 1-16.
- 倍数: integer multiplier >= 1 (defaults to 1 if blank).

A single SSQ bet costs 2 RMB, so one row costs 2 * 倍数 per draw.
Blank lines and lines starting with '#' are ignored.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import List

from .checker import normalize

BET_PRICE_RMB = 2  # official SSQ single-bet price

# Accept either Chinese or English header names.
_RED_KEYS = ("红球", "reds", "red")
_BLUE_KEYS = ("蓝球", "blue")
_MULT_KEYS = ("倍数", "multiplier", "mult", "倍投")


@dataclass(frozen=True)
class Bet:
    reds: List[str]      # 6 distinct, zero-padded "01".."33"
    blue: str            # zero-padded "01".."16"
    multiplier: int      # >= 1

    @property
    def cost(self) -> int:
        """Cost of this row for one draw, in RMB."""
        return BET_PRICE_RMB * self.multiplier


def _pick(row: dict, keys: tuple, label: str, lineno: int) -> str:
    for k in keys:
        if k in row and row[k] is not None and row[k].strip():
            return row[k].strip()
    raise ValueError(f"第{lineno}行缺少必填列「{label}」（接受表头：{'/'.join(keys)}）")


def _parse_row(row: dict, lineno: int) -> Bet:
    raw_reds = _pick(row, _RED_KEYS, "红球", lineno).split()
    if len(raw_reds) != 6:
        raise ValueError(f"第{lineno}行红球应为6个，实际{len(raw_reds)}个：{raw_reds}")
    try:
        reds = normalize(raw_reds)
        blue = f"{int(_pick(row, _BLUE_KEYS, '蓝球', lineno)):02d}"
    except (TypeError, ValueError) as e:
        raise ValueError(f"第{lineno}行号码无法解析：{e}") from e

    if len(set(reds)) != 6:
        raise ValueError(f"第{lineno}行红球有重复：{reds}")
    for r in reds:
        if not 1 <= int(r) <= 33:
            raise ValueError(f"第{lineno}行红球超出 1-33 范围：{r}")
    if not 1 <= int(blue) <= 16:
        raise ValueError(f"第{lineno}行蓝球超出 1-16 范围：{blue}")

    mult_raw = ""
    for k in _MULT_KEYS:
        if k in row and row[k] is not None and row[k].strip():
            mult_raw = row[k].strip()
            break
    try:
        multiplier = int(mult_raw) if mult_raw else 1
    except ValueError as e:
        raise ValueError(f"第{lineno}行倍数无法解析：{mult_raw!r}") from e
    if multiplier < 1:
        raise ValueError(f"第{lineno}行倍数必须 >= 1：{multiplier}")

    return Bet(reds=reds, blue=blue, multiplier=multiplier)


def parse_bets(text: str) -> List[Bet]:
    """Parse bet rows from CSV text. Raises ValueError on malformed rows."""
    # Drop blank and comment lines before handing to csv.DictReader.
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise ValueError("投注表为空")
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        raise ValueError("投注表缺少表头行")
    bets: List[Bet] = []
    # lineno is 1-based over the non-comment lines, +1 to account for the header.
    for i, row in enumerate(reader, start=2):
        bets.append(_parse_row(row, i))
    if not bets:
        raise ValueError("投注表没有任何投注行（只有表头）")
    return bets


def load_bets(path: str) -> List[Bet]:
    """Load bets from a CSV file path."""
    with open(path, encoding="utf-8-sig") as f:
        return parse_bets(f.read())

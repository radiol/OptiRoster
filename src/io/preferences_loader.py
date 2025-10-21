from __future__ import annotations

import csv
import datetime as dt
import re
from collections import defaultdict
from enum import Enum

from src.domain.types import ShiftType


class PreferenceStatus(str, Enum):
    NONE = "制限なし"
    NIGHT_FORBIDDEN = "当直不可"
    DAY_NIGHT_FORBIDDEN = "日勤・当直不可"


_WANTS_NIGHT = "当直希望"

# 例: "2025年10月 勤務希望 [10/1(水)]"
_DATE_HEAD_RE = re.compile(r"(\d{4})年(\d{1,2})月.*\[(\d{1,2})/(\d{1,2})")


def _parse_date_from_header(header: str) -> dt.date | None:
    """ヘッダが日付列なら date を返す。合わなければ None。"""
    h = (header or "").strip()
    m = _DATE_HEAD_RE.search(h)
    if not m:
        return None
    year, mm_head, mm_bracket, dd = map(int, m.groups())
    # かっこ内の月を優先(表記ぶれ対策)
    month = mm_bracket or mm_head
    return dt.date(year, month, dd)


def load_preferences_csv(path: str) -> dict[tuple[str, dt.date], PreferenceStatus]:
    """
    横持ちCSVを読み込む。
    想定ヘッダ例:
    氏名,2025年10月 勤務希望 [10/1(水)],2025年10月 勤務希望 [10/2(木)],...
    A/C列などに不要列があっても、'氏名' 列と日付ヘッダ列のみ採用する。
    空白は以下のルールで解釈する。
    - "当直希望"なし -> 制限なし
    - "当直希望"が1つでもある -> 当直不可

    戻り値: {(worker: str, date: date): PreferenceStatus}
    """
    result: dict[tuple[str, dt.date], PreferenceStatus] = {}

    # BOM付きUTF-8も想定してutf-8-sigで開く
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)  # ← カンマ区切り固定
        headers: list[str] = next(reader)

        # “氏名”列をヘッダ名で検出(位置は固定しない)
        try:
            name_col = next(i for i, h in enumerate(headers) if (h or "").strip() == "氏名")
        except StopIteration as e:
            raise ValueError("ヘッダに『氏名』列が見つかりません。") from e

        # 日付ヘッダ列だけ抽出(不要列は自然に無視される)
        date_cols: list[tuple[int, dt.date]] = []
        for i, h in enumerate(headers):
            if i == name_col:
                continue
            d = _parse_date_from_header(h)
            if d is not None:
                date_cols.append((i, d))

        if not date_cols:
            raise ValueError("日付ヘッダ(例: '2025年10月 勤務希望 [10/1(水)]')が見つかりません。")

        row_list = list(reader)
        # 1パス目: 当直希望の有無を集計
        wants_night: dict[str, bool] = defaultdict(bool)
        for row in row_list:
            if not row or len(row) <= name_col:
                continue
            worker = (row[name_col] or "").strip()
            if worker == "":
                continue

            for col_idx, _ in date_cols:
                val = (row[col_idx] if col_idx < len(row) else "").strip()
                if val == _WANTS_NIGHT:
                    wants_night[worker] = True

        # 2パス目: セルごとに"制限なし" or "当直不可" or "日勤・当直不可"を確定
        for row in row_list:
            if not row or len(row) <= name_col:
                continue
            worker = (row[name_col] or "").strip()
            if worker == "":
                continue

            for col_idx, d in date_cols:
                val = (row[col_idx] if col_idx < len(row) else "").strip()
                match (val, wants_night[worker]):
                    case ("", False) | (PreferenceStatus.NONE.value, False):
                        status = PreferenceStatus.NONE
                    case ("", True) | (PreferenceStatus.NONE.value, True):
                        status = PreferenceStatus.NIGHT_FORBIDDEN
                    case (PreferenceStatus.NIGHT_FORBIDDEN.value, _):
                        status = PreferenceStatus.NIGHT_FORBIDDEN
                    case (PreferenceStatus.DAY_NIGHT_FORBIDDEN.value, _):
                        status = PreferenceStatus.DAY_NIGHT_FORBIDDEN
                    case (_, _):
                        # 未知の文言は安全側で無視(=制限なし)
                        # "当直希望"もここに含まれる
                        status = PreferenceStatus.NONE
                result[(worker, d)] = status

    return result


def disallowed_shifts_for(status: PreferenceStatus) -> set[ShiftType]:
    if status == PreferenceStatus.NIGHT_FORBIDDEN:
        return {ShiftType.NIGHT}
    if status == PreferenceStatus.DAY_NIGHT_FORBIDDEN:
        return {ShiftType.DAY, ShiftType.NIGHT, ShiftType.AM, ShiftType.PM}
    return set()

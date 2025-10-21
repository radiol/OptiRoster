from __future__ import annotations

import csv


def load_max_assignments_csv(path: str) -> dict[tuple[str, str], int | None]:
    """
    CSV 形式:
    Name,大学,病院A,病院B,病院C,...
    診断01,,,,
    診断02,2,,,
    診断03,,0,,   ← 0 は「禁止」の意味で上限 0
    戻り値:
        {(worker, hospital): Optional[int]}
            - None : 上限なし(空欄)
            - int  : 最大回数
    """
    result: dict[tuple[str, str], int | None] = {}

    # BOM付きUTF-8も想定
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        if not headers or headers[0].strip() != "Name":
            raise ValueError("ヘッダの先頭は 'Name' である必要があります。")

        hospitals = [h.strip() for h in headers[1:]]

        for row_idx, row in enumerate(reader, start=2):  # 行番号を持っておくとエラー時に便利
            if not row:
                continue
            name = (row[0] or "").strip()
            if name == "":
                continue

            for col, hosp in enumerate(hospitals, start=1):
                raw = (row[col] if col < len(row) else "").strip()
                if raw == "":
                    cap: int | None = None
                else:
                    try:
                        cap = int(raw)
                        if cap < 0:
                            raise ValueError(
                                f"{path}:{row_idx}行目 {hosp}列: 負の値 {cap} は無効です"
                            )
                    except ValueError as e:
                        raise ValueError(
                            f"{path}:{row_idx}行目 {hosp}列: "
                            f"数値または空欄を期待しましたが '{raw}' が見つかりました"
                        ) from e
                result[(name, hosp)] = cap

    return result

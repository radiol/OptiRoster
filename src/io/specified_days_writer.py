"""Write dict[str, list[int]] to a specified_days.toml file."""

from __future__ import annotations

import tomlkit


def dump_specified_days(data: dict[str, list[int]], path: str) -> None:
    """Write specified-days configuration to a TOML file.

    Args:
        data: Mapping of hospital name to list of day numbers.
        path: Output file path.
    """
    doc = tomlkit.document()
    aot = tomlkit.aot()

    for name, days in data.items():
        tbl = tomlkit.table()
        tbl.add("name", name)
        dates = tomlkit.array()
        for d in days:
            dates.append(d)
        tbl.add("dates", dates)
        aot.append(tbl)

    doc.add("hospitals", aot)
    with open(path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))

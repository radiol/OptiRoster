"""Write list[Hospital] to a hospitals.toml file."""

from __future__ import annotations

import tomlkit

from src.domain.types import Hospital


def dump_hospitals(hospitals: list[Hospital], path: str) -> None:
    """Write hospital configuration to a TOML file.

    Args:
        hospitals: List of Hospital domain objects.
        path: Output file path.
    """
    doc = tomlkit.document()
    aot = tomlkit.aot()

    for h in hospitals:
        tbl = tomlkit.table()
        tbl.add("name", h.name)
        tbl.add("is_remote", h.is_remote)
        tbl.add("is_university", h.is_university)

        if h.demand_rules:
            shifts_aot = tomlkit.aot()
            for rule in h.demand_rules:
                st = tomlkit.table()
                st.add("shift_type", rule.shift_type.value)
                weekdays = tomlkit.array()
                for wd in rule.weekdays:
                    weekdays.append(wd.value)
                st.add("weekdays", weekdays)
                st.add("frequency", rule.frequency.value)
                shifts_aot.append(st)
            tbl.add("shifts", shifts_aot)

        aot.append(tbl)

    doc.add("hospitals", aot)
    with open(path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))

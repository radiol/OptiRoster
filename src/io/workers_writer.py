"""Write list[Worker] to a workers.toml file."""

from __future__ import annotations

import tomlkit

from src.domain.types import Worker


def dump_workers(workers: list[Worker], path: str) -> None:
    """Write worker configuration to a TOML file.

    Args:
        workers: List of Worker domain objects.
        path: Output file path.
    """
    doc = tomlkit.document()
    aot = tomlkit.aot()

    for w in workers:
        tbl = tomlkit.table()
        tbl.add("name", w.name)
        tbl.add("is_diagnostic_specialist", w.is_diagnostic_specialist)

        if w.assignments:
            assignments_aot = tomlkit.aot()
            for a in w.assignments:
                at = tomlkit.table()
                at.add("hospital", a.hospital)
                weekdays = tomlkit.array()
                for wd in a.weekdays:
                    weekdays.append(wd.value)
                at.add("weekdays", weekdays)
                at.add("shift_type", a.shift_type.value)
                assignments_aot.append(at)
            tbl.add("assignments", assignments_aot)

        aot.append(tbl)

    doc.add("workers", aot)
    with open(path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))

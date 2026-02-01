"""Write dict[tuple[str, str], int | None] to a max-assignments CSV file."""

from __future__ import annotations

import csv


def dump_max_assignments_csv(data: dict[tuple[str, str], int | None], path: str) -> None:
    """Write max-assignments configuration to a CSV file.

    Args:
        data: Mapping of (worker, hospital) to cap value (None = no limit).
        path: Output file path.
    """
    # Collect workers and hospitals in insertion order.
    workers: list[str] = []
    hospitals: list[str] = []
    workers_seen: set[str] = set()
    hospitals_seen: set[str] = set()

    for worker, hospital in data:
        if worker not in workers_seen:
            workers.append(worker)
            workers_seen.add(worker)
        if hospital not in hospitals_seen:
            hospitals.append(hospital)
            hospitals_seen.add(hospital)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", *hospitals])

        for worker in workers:
            row = [worker]
            for hospital in hospitals:
                cap = data.get((worker, hospital))
                row.append("" if cap is None else str(cap))
            writer.writerow(row)

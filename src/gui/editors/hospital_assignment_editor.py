"""Hospital-centric max-assignments editor.

Replaces the flat CSV grid editor with a hospital-grouped view
where each hospital section lists its assignable workers with
a 4-option toggle: unlimited / forbidden / 1 / 2.
"""

from __future__ import annotations

from collections import OrderedDict

from src.domain.types import Worker


def build_hospital_worker_map(workers: list[Worker]) -> dict[str, list[str]]:
    """Build an ordered mapping of hospital -> [worker_name, ...].

    Only worker-hospital pairs defined in workers.toml assignments are included.
    Workers appear in the order they are listed in `workers`.
    Duplicate hospital entries per worker (same hospital, different weekday) are
    deduplicated so each worker appears at most once per hospital.

    Args:
        workers: List of Worker domain objects.

    Returns:
        Dict mapping hospital name to ordered list of worker names.
    """
    result: dict[str, list[str]] = OrderedDict()
    for worker in workers:
        seen_hospitals: set[str] = set()
        for rule in worker.assignments:
            hosp = rule.hospital
            if hosp in seen_hospitals:
                continue
            seen_hospitals.add(hosp)
            if hosp not in result:
                result[hosp] = []
            result[hosp].append(worker.name)
    return result

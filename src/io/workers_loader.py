import tomllib

from src.domain.types import ShiftType, Weekday, Worker, WorkerAssignmentRule


def load_workers(config_path: str) -> list[Worker]:
    """Load worker configuration from a TOML file.

    Args:
        config_path (str): Path to the TOML configuration file.

    Returns:
        List[Worker]: List of loaded workers.
    """
    workers: list[Worker] = []

    with open(config_path, "rb") as f:
        config = tomllib.loads(f.read().decode("utf-8-sig"))
        for worker in config.get("workers", []):
            name = worker["name"]
            is_diagnostic_specialist = worker.get("is_diagnostic_specialist", False)
            assignments = []
            for assignment in worker.get("assignments", []):
                hospital = assignment["hospital"]
                weekdays = [Weekday(day) for day in assignment.get("weekdays", [])]
                shift_type = ShiftType(assignment["shift_type"])
                assignments.append(
                    WorkerAssignmentRule(
                        hospital=hospital,
                        weekdays=weekdays,
                        shift_type=shift_type,
                    )
                )
            workers.append(
                Worker(
                    name=name,
                    is_diagnostic_specialist=is_diagnostic_specialist,
                    assignments=assignments,
                )
            )
            # print(f"Loaded config for worker: {name}")

    return workers

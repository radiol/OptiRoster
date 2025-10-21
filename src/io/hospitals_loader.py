import tomllib

from src.domain.types import Frequency, Hospital, HospitalDemandRule, ShiftType, Weekday


def load_hospitals(config_path: str) -> list[Hospital]:
    """Load hospital configuration from a TOML file.

    Args:
        config_path (str): Path to the TOML configuration file.

    Returns:
        List[Hospital]: Parsed configuration data.
    """

    data = []

    with open(config_path, "rb") as f:
        config = tomllib.loads(f.read().decode("utf-8-sig"))
        for hospital in config.get("hospitals", []):
            name = hospital["name"]
            is_remote = hospital.get("is_remote", False)
            is_university = hospital.get("is_university", False)
            shifts = []
            for shift in hospital.get("shifts", []):
                shift_type = ShiftType(shift["shift_type"])
                weekdays = [Weekday(day) for day in shift.get("weekdays", [])]
                frequency = Frequency(shift.get("frequency", "毎週"))
                shifts.append(
                    HospitalDemandRule(
                        shift_type=shift_type, weekdays=weekdays, frequency=frequency
                    )
                )
            data.append(
                Hospital(
                    name=name,
                    is_remote=is_remote,
                    is_university=is_university,
                    demand_rules=shifts,
                )
            )
            # print(f"Loaded config for hospital: {name}")

    return data

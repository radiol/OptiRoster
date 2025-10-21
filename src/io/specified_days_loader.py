import tomllib


def load_specified_days(config_path: str) -> dict[str, list[int]]:
    """Load specified days configuration from a TOML file.

    Args:
        config_path (str): Path to the TOML configuration file.
    Returns:
        dict[str, List[int]]: Parsed configuration data.
    """

    with open(config_path, "rb") as f:
        config = tomllib.loads(f.read().decode("utf-8-sig"))
        specified_days = dict()
        for hospital in config.get("hospitals", []):
            name = hospital.get("name")
            days = hospital.get("dates", [])
            if name:
                specified_days[name] = days

    return specified_days

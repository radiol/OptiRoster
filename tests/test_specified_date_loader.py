import textwrap

from src.io.specified_days_loader import load_specified_days


def write_toml(tmp_path, content: str):
    p = tmp_path / "specified_days.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_basic_two_hospitals(tmp_path):
    toml = """
    [[hospitals]]
    name = "A病院"
    dates = [1, 5, 12]

    [[hospitals]]
    name = "B病院"
    dates = [3, 20]
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    assert got == {
        "A病院": [1, 5, 12],
        "B病院": [3, 20],
    }


def test_no_hospitals_key_returns_empty_dict(tmp_path):
    toml = """
    # hospitals テーブルなし
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    assert got == {}


def test_hospital_without_name_is_skipped(tmp_path):
    toml = """
    [[hospitals]]
    # name なし → スキップされる
    dates = [10]

    [[hospitals]]
    name = "C病院"
    dates = [2, 4]
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    assert got == {"C病院": [2, 4]}


def test_missing_dates_becomes_empty_list(tmp_path):
    """
    dates が無ければ [] になる
    """
    toml = """
    [[hospitals]]
    name = "D病院"
    # dates 無し
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    assert "D病院" in got
    assert got["D病院"] == []


def test_empty_dates_list_is_kept(tmp_path):
    toml = """
    [[hospitals]]
    name = "E病院"
    dates = []
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    assert got == {"E病院": []}


def test_duplicate_names_last_wins(tmp_path):
    toml = """
    [[hospitals]]
    name = "F病院"
    dates = [1]

    [[hospitals]]
    name = "F病院"
    dates = [2, 3]
    """
    path = write_toml(tmp_path, toml)
    got = load_specified_days(str(path))
    # 後勝ち(辞書上書き)
    assert got == {"F病院": [2, 3]}

import datetime as dt
import importlib
import sys

import pulp
import pytest


def _reset_registry_and_module():
    """
    レジストリと関連モジュールをきれいにして、毎テスト同じ初期状態にする。
    """
    import src.constraints.base as base

    base.constraint_registry.clear()

    # 以前に import 済みのプラグインをモジュールキャッシュから外す
    for mod in [
        "src.constraints.c01_one_person_per_hospital",
    ]:
        sys.modules.pop(mod, None)

    # autoimport を再読み込み(__path__参照のため)
    sys.modules.pop("src.constraints.autoimport", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_registry_is_empty_until_plugin_is_imported():
    from src.constraints.base import all_constraints

    # 何も import していない間は空
    assert all_constraints() == []

    # プラグインを import すると register() が走る
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    names = [c.name for c in all_constraints()]
    assert "one_person_per_hospital" in names


def test_autoimport_loads_plugins_and_registers():
    from src.constraints.autoimport import auto_import_all
    from src.constraints.base import all_constraints

    # まだ空
    assert all_constraints() == []

    # 自動読み込みを実行
    auto_import_all()

    names = [c.name for c in all_constraints()]
    assert "one_person_per_hospital" in names


def test_one_person_per_hospital_constraint_applies_and_solves():
    """
    x[(h,w,d,s)] を2変数(同一 (h,d)、異なる worker/shift)だけ作り、
    制約適用後は Σ_{w,s} x[h,w,d,s] == 1 が張られて解けることを確認。
    """
    # プラグインを読み込み(registerさせる)
    import src.constraints.c01_one_person_per_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    # ダミーの x を構築
    h = "テスト病院"
    d = dt.date(2025, 9, 1)
    # 2人が同じ日に別シフトで候補にいる状況を模す
    x = {}
    x[(h, "山田", d, "日勤")] = pulp.LpVariable("x_yamada", 0, 1, cat="Binary")
    x[(h, "佐藤", d, "当直")] = pulp.LpVariable("x_sato", 0, 1, cat="Binary")

    # モデル構築:とりあえず「割当数最大化」
    model = pulp.LpProblem("test", pulp.LpMaximize)
    model += pulp.lpSum(x.values())

    ctx = {"required_hd": {(h, d)}}

    # すべての登録済み制約を適用(今回1つの想定)
    for c in all_constraints():
        c.apply(model, x, ctx)

    # 求解して、ちょうど1個が選ばれることを確認
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    chosen = [k for k, v in x.items() if pulp.value(v) == 1]
    assert len(chosen) == 1  # どちらか片方のみ選ばれる


def test_constraint_name_is_printable_after_autoimport(capsys):
    """
    main でやるのと同様に、auto_import_all → all_constraints で name を print できることを確認。
    """
    from src.constraints.autoimport import auto_import_all
    from src.constraints.base import all_constraints

    auto_import_all()

    for c in all_constraints():
        print(c.name)

    out = capsys.readouterr().out
    # プラグイン名が出力に含まれる
    assert "one_person_per_hospital" in out

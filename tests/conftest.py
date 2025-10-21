import importlib
import sys

import pytest

import src.constraints.base as base


def _reset_registry_and_modules(module_paths: list[str] | None = None):
    """レジストリをクリアし、指定モジュールを再importできる状態に戻す"""
    base.constraint_registry.clear()
    if module_paths:
        for m in module_paths:
            sys.modules.pop(m, None)
    importlib.invalidate_caches()


@pytest.fixture
def ensure_constraint():
    """
    テストごとに制約モジュールを再importし、対象制約を返すフィクスチャ。

    使い方:
        def test_xxx(ensure_constraint):
            c = ensure_constraint(
                "src.constraints.s02_soft_no_night_remote_daypm_same_day",
                "soft_no_night_remote_daypm_same_day",
            )
            ...
    """

    def _loader(module_path: str, constraint_name: str):
        # クリアして対象モジュールを再import
        _reset_registry_and_modules([module_path])
        importlib.import_module(module_path)

        from src.constraints.base import all_constraints

        matches = [c for c in all_constraints() if c.name == constraint_name]
        assert matches, f"{constraint_name} not registered in {module_path}"
        return matches[0]

    yield _loader

    # 後片付け
    _reset_registry_and_modules()

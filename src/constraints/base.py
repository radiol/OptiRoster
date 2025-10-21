# プラグイン化の基底プログラム
from src.constraints.base_impl import ConstraintBase

constraint_registry = []  # 登録された制約条件のリスト


def register(constraint: ConstraintBase) -> None:
    constraint_registry.append(constraint)


def all_constraints() -> list[ConstraintBase]:
    return list(constraint_registry)

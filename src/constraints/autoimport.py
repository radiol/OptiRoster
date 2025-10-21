import importlib
import pkgutil


def auto_import_all() -> None:
    # この関数を呼ぶと constraints パッケージ配下のモジュールを全て import
    from . import __path__ as pkg_path  # constraints パッケージの検索パス

    for m in pkgutil.iter_modules(pkg_path):
        name = m.name
        if name.startswith("_"):
            continue
        # base.py / autoimport.py 自体はスキップ
        if name in {"base", "base_impl", "autoimport"}:
            continue
        importlib.import_module(f"src.constraints.{name}")

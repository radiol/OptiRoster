"""勤務表自動生成システム

病院勤務スケジュールを最適化問題として解決し、
最適な勤務割り当てを自動生成するシステム。
"""

try:
    from importlib.metadata import version

    __version__ = version("optiroster")
except (ImportError, Exception):
    # Fallback for development installs or when package is not installed
    __version__ = "0.3.0"

__all__ = ["__version__"]

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import pulp
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from src.constraints.base import all_constraints
from src.domain.context import Context


def _get_constraint_summary(source: str) -> str:
    """制約のソース名からsummaryを取得"""
    for constraint in all_constraints():
        if constraint.name == source:
            return constraint.summary
    return source  # 見つからない場合はsource名を返す


def _iter_penalty_rows(ctx: Context) -> Iterable[dict[str, Any]]:
    """
    ctx からペナルティの行を取り出し、評価値(var の最適値 * weight * source毎の係数)を付与して返す。
    サポート:
        - ctx["penalties"] に PenaltyItem(var, weight, meta, source) のタプル配列
    """
    scale = ctx.get("penalty_source_scale", {})

    for item in ctx.get("penalties", []):
        var, weight, meta, source = item
        val = pulp.value(var)
        source_name = source or "unknown"
        yield {
            "source": source_name,
            "summary": _get_constraint_summary(source_name),
            "var_name": getattr(var, "name", str(var)),
            "value": float(val) if val is not None else None,
            "weight": weight * scale.get(source_name, 1.0),
            "penalty": (weight * float(val)) if val is not None else None,
            "meta": meta or {},
        }


def print_penalties_rich(ctx: Context, top_n: int | None = 30) -> None:
    console = Console()
    rows = list(
        data
        for data in _iter_penalty_rows(ctx)
        if data["penalty"] is not None and data["penalty"] != 0
    )
    if not rows:
        console.print("[bold green]ペナルティは発生していません。[/]")
        return

    # 総計 & サマリ別集計
    total = 0.0
    by_summary: dict[str, float] = defaultdict(float)
    for r in rows:
        p = r["penalty"]
        total += p
        by_summary[r["summary"]] += p

    # 1) サマリ(総計 & 制約別)
    summary = Table(title="Penalty Summary", show_lines=False)
    summary.add_column("Constraint", justify="left")
    summary.add_column("Total", justify="right")
    for s, v in sorted(by_summary.items(), key=lambda kv: -kv[1]):
        summary.add_row(str(s), f"{v:.3f}")
    summary_panel = Panel(summary, title=f"[b]Total Penalty = {total:.3f}[/b]", border_style="cyan")

    # 2) 明細テーブル(上位 N)
    detail = Table(title=f"Penalty Items (Top {top_n if top_n else 'All'})", show_lines=False)
    detail.add_column("#", justify="right", no_wrap=True)
    detail.add_column("Constraint", no_wrap=True)
    detail.add_column("Var", overflow="fold")
    detail.add_column("Val", justify="right")
    detail.add_column("Weight", justify="right")
    detail.add_column("Penalty", justify="right")
    detail.add_column("Meta", overflow="fold")

    sorted_rows = sorted(rows, key=lambda r: (r["penalty"]), reverse=True)
    if top_n:
        sorted_rows = sorted_rows[:top_n]

    for i, r in enumerate(sorted_rows, 1):
        meta_str = ", ".join(f"{k}={v}" for k, v in r["meta"].items())
        detail.add_row(
            str(i),
            str(r["summary"]),
            r["var_name"],
            f"{(r['value'] if r['value'] is not None else 0):.1f}",
            f"{r['weight']:.1f}",
            f"{(r['penalty'] if r['penalty'] is not None else 0):.1f}",
            meta_str,
        )

    console.print(Group(summary_panel, detail))

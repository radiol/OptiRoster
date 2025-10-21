from collections import defaultdict
from datetime import date
from itertools import product

import pulp

from src.domain.context import VarKey
from src.domain.types import Hospital, ShiftType, Weekday, Worker
from src.model.demand import compute_required_map


class VariableBuilder:
    def __init__(
        self,
        hospitals: list[Hospital],
        workers: list[Worker],
        days: list[date],
    ):
        self.hospitals = hospitals  # List[Hospital]
        self.workers = workers  # List[Worker]
        self.days = days  # List[date]
        self.shift_types = list(ShiftType)
        self.weekdays = list(Weekday)  # [MONDAY..SUNDAY]

        # VarKey(h,w,d,s) -> 0/1
        self.ub: dict[VarKey, int] = defaultdict(int)

    def init_all_zero(self) -> None:
        for h, w, d, s in product(self.hospitals, self.workers, self.days, self.shift_types):
            self.ub[VarKey(h.name, w.name, d, s)] = 0

    def elevate_by_workers(self, worker_list: list[Worker]) -> None:
        """workers.tomlの内容でUBを1にする(候補化)"""
        for w in worker_list:
            if not w.assignments:
                continue
            for a, d in product(w.assignments, self.days):
                if self.weekdays[d.weekday()] in a.weekdays and a.shift_type in self.shift_types:
                    self.ub[VarKey(a.hospital, w.name, d, a.shift_type)] = 1

    def restrict_by_hospitals(
        self, hospital_list: list[Hospital], specified_days: dict[str, list[int]]
    ) -> None:
        """
        hospitals.tomlの需要で不要枠をUB=0に戻す。
        日 x シフトの集合で厳密にフィルタリングする。
        Args:
            hospital_list (List[Hospital]): 対象病院リスト
            specified_days (Dict[str, List[int]]): 病院名をキー、日付(int)のリストを値とする辞書
                specified_YYYY_MM.tomlからロード。
                例: {"病院A": [1, 15], "病院B": [3, 17, 30]}
        """
        required_map = compute_required_map(hospital_list, self.days, self.weekdays, specified_days)
        for h, w, d, s in product(hospital_list, self.workers, self.days, self.shift_types):
            needed = required_map.get((h.name, d), set())
            key = VarKey(h.name, w.name, d, s)
            if s not in needed and key in self.ub:
                self.ub[key] = 0

    def filter_by_max_assignments(self, max_assignments: dict[tuple[str, str], int | None]) -> None:
        """
        最大勤務可能数による変数フィルタリング。
        max_assignments[(worker, hospital)] == 0 の場合、
        該当する(worker, hospital)の全ての変数をUB=0に設定する。

        Args:
            max_assignments: (worker, hospital)をキーとした最大勤務可能数の辞書
                値が0の場合、その組み合わせでの勤務を禁止する
        """
        for (worker_name, hospital_name), max_count in max_assignments.items():
            if max_count != 0:
                continue
            # 最大勤務数が0の場合、該当する全ての変数をUB=0に設定
            # 既存のキーのみを対象にして、新しいエントリを作成しないようにする
            for d, s in product(self.days, self.shift_types):
                key = VarKey(hospital_name, worker_name, d, s)
                if key in self.ub:
                    self.ub[key] = 0

    def materialize(self, name: str = "x") -> dict[VarKey, pulp.LpVariable]:
        """UB=1のものだけPuLP変数にする"""
        x = {}
        for var_key, ub in self.ub.items():
            if ub == 1:
                h, w, d, s = var_key
                date_token = d.strftime("%Y%m%d")  # YYYYMMDD形式に変換
                x[VarKey(h, w, d, s)] = pulp.LpVariable(
                    f"{name}__{h}__{w}__{date_token}__{s.value}",
                    lowBound=0,
                    upBound=1,
                    cat="Binary",
                )
        return x

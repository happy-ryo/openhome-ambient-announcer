"""組織 state → 正規化イベント JSON ブリッジ (docs/design.md §2.2 / §5.1).

責務:
- 組織 state を **読み取り専用** で参照する (state を書き換えない — design §1.3 / §4.4)。
- プロジェクト側が与える normalizer で正規化イベント (OrgEvent) へ変換する。
  「どのイベントを拾うか」はプロジェクト固有 (design §5.2) なので注入する。
- 共有イベント JSON へ **原子的** に書き出す (部分書き込み回避 — design §4.2 V-5)。
- public 衛生の単一関門として、絶対パス等の内部表現の漏れを検出する (design §6)。

本ブリッジは Ability へ向けた一方向の出力のみ。組織へ書き戻す経路は持たない。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .envelope import OrgEvent

# 内部表現の漏れを検出するパターン (public 衛生 — design §6)
_LEAK_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"),             # Windows 絶対パス (例 C:\...)
    re.compile(r"(?:^|[\s\"'])/[\w./-]+"),  # POSIX 絶対パス
)

StateSource = Callable[[], object]
Normalizer = Callable[[object], Iterable[OrgEvent]]


class PublicHygieneError(ValueError):
    """正規化イベントに public へ出せない内部表現が混入したときに送出。"""


class StateBridge:
    """state を読み取り、正規化イベント JSON を原子的に書き出す共有基盤。"""

    def __init__(
        self,
        state_source: StateSource,
        normalizer: Normalizer,
        out_path: str | os.PathLike,
    ) -> None:
        self._state_source = state_source
        self._normalizer = normalizer
        self._out_path = Path(out_path)

    @property
    def out_path(self) -> Path:
        return self._out_path

    def export(self) -> list[OrgEvent]:
        """state を read-only 参照し、正規化イベント JSON を書き出して返す。"""
        snapshot = self._state_source()  # 読み取りのみ。書き戻さない。
        events = list(self._normalizer(snapshot))
        self._assert_public_clean(events)
        self._write_atomic(events)
        return events

    def _write_atomic(self, events: Sequence[OrgEvent]) -> None:
        self._out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"events": [e.to_dict() for e in events]}
        tmp = self._out_path.with_suffix(self._out_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._out_path)  # 原子的差し替え (design §4.2 V-5)

    @staticmethod
    def _assert_public_clean(events: Iterable[OrgEvent]) -> None:
        for ev in events:
            for value in (ev.subject, ev.summary):
                for pat in _LEAK_PATTERNS:
                    if pat.search(value):
                        raise PublicHygieneError(
                            f"event {ev.id!r} に内部表現の疑い: {value!r}"
                        )

"""polling + 既読集合による冪等読み上げ基盤 (docs/design.md §2.3 / §5.1).

OpenHome の Background Ability が `while True` + `session_tasks.sleep()` で
共有イベント JSON を polling する公式パターン (design §4.1) を、ローカルで
検証可能な純ロジックとして切り出したもの。

- 各イベントの安定 id を既読集合と突き合わせ、未読のみを返す (冪等 — design §2.3)。
- 既読集合はファイルへ永続でき、Ability 再起動をまたいだ重複排除を模す
  (design §4.2 V-3 / §8)。実 SDK では write_file()/read_file() に相当。

本基盤は発話しない。発話整形・流量制御はプロジェクト側の責務 (design §5.2)。
"""

from __future__ import annotations

import json
from pathlib import Path

from .envelope import OrgEvent


class EventPoller:
    """共有イベント JSON を polling し、未読イベントのみを返す。"""

    def __init__(
        self,
        events_path: str | Path,
        seen_path: str | Path | None = None,
    ) -> None:
        self._events_path = Path(events_path)
        self._seen_path = Path(seen_path) if seen_path else None
        self._seen: set[str] = self._load_seen()

    @property
    def seen_ids(self) -> frozenset[str]:
        return frozenset(self._seen)

    def poll_once(self) -> list[OrgEvent]:
        """JSON を 1 回読み、まだ読み上げていないイベントだけを返す。"""
        events = self._read_events()
        fresh = [e for e in events if e.id not in self._seen]
        for ev in fresh:
            self._seen.add(ev.id)
        if fresh:
            self._persist_seen()
        return fresh

    def _read_events(self) -> list[OrgEvent]:
        if not self._events_path.exists():
            return []
        try:
            with open(self._events_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # 部分書き込み等は次回ポーリングで回収する (design §4.2 V-5)
            return []
        return [OrgEvent.from_dict(d) for d in data.get("events", [])]

    def _load_seen(self) -> set[str]:
        if not self._seen_path or not self._seen_path.exists():
            return set()
        try:
            with open(self._seen_path, "r", encoding="utf-8") as fh:
                return set(json.load(fh).get("seen", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _persist_seen(self) -> None:
        if not self._seen_path:
            return
        self._seen_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._seen_path.with_suffix(self._seen_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"seen": sorted(self._seen)}, fh, ensure_ascii=False, indent=2)
        tmp.replace(self._seen_path)

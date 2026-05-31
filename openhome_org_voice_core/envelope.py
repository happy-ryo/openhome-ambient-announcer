"""正規化イベント・エンベロープ (docs/design.md §3.2).

組織内部の state スキーマを **そのまま写さず**、public に出せる最小の抽象表現へ
正規化する。内部フック名・絶対パス・生の state カラム・内部 ID の生値は入れない
(抽象化の責務はブリッジが負う — design §2.2 / §6)。
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

# 監視対象イベント種別 (design §3.1)
EVENT_TYPES = (
    "task_completed",
    "blocker_raised",
    "approval_pending",
    "task_started",
    "milestone_reached",
)

# 優先度 (design §3.2)
PRIORITIES = ("low", "normal", "high")


def stable_event_id(event_type: str, subject: str, marker: str = "") -> str:
    """同一の状態遷移に対して常に同じ id を生成する (冪等性の鍵 — design §3.2).

    内部 ID の生値を晒さないよう、抽象キーをハッシュして安定 id を作る。
    再起動・ポーリング重複でも同じイベントは同じ id になり、既読集合と
    突き合わせて二重読み上げを防ぐ。
    """
    raw = f"{event_type}|{subject}|{marker}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    return f"evt-{digest}"


@dataclass(frozen=True)
class OrgEvent:
    """組織の状態遷移を表す正規化イベント (design §3.2 エンベロープ)。"""

    id: str
    type: str
    priority: str
    subject: str
    summary: str
    ts: str
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {self.type!r}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"unknown priority: {self.priority!r}")

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d["extra"]:
            d.pop("extra")
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "OrgEvent":
        return cls(
            id=data["id"],
            type=data["type"],
            priority=data["priority"],
            subject=data["subject"],
            summary=data.get("summary", ""),
            ts=data["ts"],
            extra=data.get("extra", {}),
        )

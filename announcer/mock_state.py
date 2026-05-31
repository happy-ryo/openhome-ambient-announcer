"""PoC 用の public-safe な組織 state スタブと normalizer (docs/design.md §6 / §7 M2).

M2 はローカル完結。実 state には繋がず (design §7 スコープ)、概念レベルの
モック state を用いる。public 衛生 (design §6) に従い、マシン固有の絶対パス・
内部フック名・state スキーマの生写し・内部 ID の生値は **一切含めない**。
役割やゲート・承認の概念のみを抽象ラベルで表現する。

normalize() が「どのイベントを拾うか」(本件固有 — design §5.2) を担う。
"""

from __future__ import annotations

from copy import deepcopy

from openhome_org_voice_core import OrgEvent, stable_event_id

# 決定論的な PoC のための固定タイムスタンプ (実接続では発生時刻を用いる)
_DEFAULT_TS = "2026-05-31T00:00:00Z"

# 組織 state の概念モデル → 正規化イベント種別・優先度 (design §3.1)
_STATE_TO_EVENT = {
    "completed": ("task_completed", "normal"),
    "blocked": ("blocker_raised", "high"),
    "approval_pending": ("approval_pending", "high"),
    "milestone": ("milestone_reached", "normal"),
    "started": ("task_started", "low"),
}

# public-safe な初期スナップショット (概念ラベルのみ)
_INITIAL_ITEMS = [
    {"label": "設計ドキュメント整備", "state": "completed"},
    {"label": "認証フローの実装", "state": "blocked", "detail": "外部依存の解決待ち"},
    {"label": "リリース可否の判断", "state": "approval_pending"},
]


class MockOrgState:
    """読み取り専用で参照される組織 state のモック。

    ブリッジは snapshot() の戻り値のみを参照し、state を書き換えない
    (read-only 契約 — design §1.3 / §4.4)。
    """

    def __init__(self, items: list[dict] | None = None) -> None:
        self._items = deepcopy(items if items is not None else _INITIAL_ITEMS)

    def snapshot(self) -> list[dict]:
        """現在の state のコピーを返す (呼び出し側からの改変を防ぐ)。"""
        return deepcopy(self._items)

    def advance(self, new_items: list[dict]) -> None:
        """PoC ドライバが state 遷移をシミュレートするための更新口。"""
        self._items = deepcopy(new_items)


def normalize(snapshot: list[dict]) -> list[OrgEvent]:
    """state スナップショットを正規化イベントへ変換する (本件固有の選択)。"""
    events: list[OrgEvent] = []
    for item in snapshot:
        mapping = _STATE_TO_EVENT.get(item.get("state", ""))
        if mapping is None:
            continue  # 監視対象外の状態は無視
        event_type, priority = mapping
        subject = item["label"]
        summary = item.get("detail", "")
        events.append(
            OrgEvent(
                id=stable_event_id(event_type, subject),
                type=event_type,
                priority=priority,
                subject=subject,
                summary=summary,
                ts=item.get("ts", _DEFAULT_TS),
            )
        )
    return events

"""一般イベントの発話テンプレート (docs/design.md §3.3).

読み上げは **短く・能動的・割り込み前提**。発話文は state の生データではなく
正規化済みの subject / summary を用いる (design §3.3)。

このモジュールが「発話文面の単一の真実」。単体テストはこの出力を固定し、
回帰 (文面の意図しない変化) を検出する。
"""

from __future__ import annotations

from openhome_org_voice_core import OrgEvent

# イベント種別 → 発話テンプレート (design §3.3)
TEMPLATES = {
    "task_completed": "{subject} が完了しました。",
    "blocker_raised": "ブロッカーです。{subject} が停止しました。{summary}",
    "approval_pending": "承認待ちが発生しました。{subject}。確認をお願いします。",
    "milestone_reached": "{subject} が {summary} に到達しました。",
    # task_started/dispatched は低優先 (冗長なら抑制可 — design §3.1)
    "task_started": "{subject} に着手しました。",
}

# 高優先度: send_interrupt_signal() で即時割り込み (design §3.3)
HIGH_PRIORITY_TYPES = ("blocker_raised", "approval_pending")


def render_event(event: OrgEvent) -> str:
    """単一イベントを発話文字列へ整形する。"""
    template = TEMPLATES.get(event.type)
    if template is None:
        raise KeyError(f"no template for event type: {event.type!r}")
    text = template.format(subject=event.subject, summary=event.summary)
    # summary 無しテンプレで末尾に空白が残る場合を整える
    return text.replace("  ", " ").strip()


def render_batch(events) -> str:
    """多数同時イベントのまとめ読み上げ (design §3.3 バッチ)。

    「更新が {n} 件あります。完了 {a} 件、ブロッカー {b} 件、承認待ち {c} 件です。」
    """
    events = list(events)
    n = len(events)
    a = sum(1 for e in events if e.type == "task_completed")
    b = sum(1 for e in events if e.type == "blocker_raised")
    c = sum(1 for e in events if e.type == "approval_pending")
    return (
        f"更新が {n} 件あります。"
        f"完了 {a} 件、ブロッカー {b} 件、承認待ち {c} 件です。"
    )

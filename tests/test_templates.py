"""主要イベントの発話文面を固定する単体テスト (docs/design.md §3.3).

文面の意図しない変化 (回帰) を検出するため、期待文字列を厳密に固定する。
"""

import pytest

from announcer.templates import render_batch, render_event
from openhome_org_voice_core import OrgEvent


def _event(type_, subject, summary="", priority="normal"):
    return OrgEvent(
        id="evt-test",
        type=type_,
        priority=priority,
        subject=subject,
        summary=summary,
        ts="2026-05-31T00:00:00Z",
    )


@pytest.mark.parametrize(
    "event, expected",
    [
        (
            _event("task_completed", "設計ドキュメント整備"),
            "設計ドキュメント整備 が完了しました。",
        ),
        (
            _event("blocker_raised", "認証フローの実装", "外部依存の解決待ち", "high"),
            "ブロッカーです。認証フローの実装 が停止しました。外部依存の解決待ち",
        ),
        (
            _event("approval_pending", "リリース可否の判断", priority="high"),
            "承認待ちが発生しました。リリース可否の判断。確認をお願いします。",
        ),
        (
            _event("milestone_reached", "ロードマップ M2", "PoC scaffold 完了"),
            "ロードマップ M2 が PoC scaffold 完了 に到達しました。",
        ),
        (
            _event("task_started", "コードレビュー対応", priority="low"),
            "コードレビュー対応 に着手しました。",
        ),
    ],
)
def test_render_event_fixed_phrasing(event, expected):
    assert render_event(event) == expected


def test_render_batch_summary():
    events = [
        _event("task_completed", "A"),
        _event("task_completed", "B"),
        _event("blocker_raised", "C", priority="high"),
        _event("approval_pending", "D", priority="high"),
        _event("milestone_reached", "E"),
    ]
    assert render_batch(events) == (
        "更新が 5 件あります。完了 2 件、ブロッカー 1 件、承認待ち 1 件です。"
    )


def test_unknown_event_type_raises():
    with pytest.raises(ValueError):
        _event("not_a_real_type", "X")

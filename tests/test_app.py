"""エンドツーエンドの流量制御テスト (docs/design.md §2.3 / §3.3).

state → ブリッジ → polling → 発話(モック) の結線を通し、
高優先度の即時割り込み・冪等性・バッチ要約を検証する。
"""

from announcer import AmbientAnnouncer
from announcer.mock_state import MockOrgState, normalize
from openhome_org_voice_core import EventPoller, MockSpeaker, StateBridge


def _wire(tmp_path, state, batch_threshold=3):
    events_path = tmp_path / "events.json"
    seen_path = tmp_path / "seen.json"
    bridge = StateBridge(state.snapshot, normalize, events_path)
    poller = EventPoller(events_path, seen_path)
    speaker = MockSpeaker()
    announcer = AmbientAnnouncer(poller, speaker, batch_threshold=batch_threshold)
    return bridge, announcer, speaker


def test_initial_tick_speaks_all_and_interrupts_high(tmp_path):
    state = MockOrgState()  # completed + blocked + approval_pending
    bridge, announcer, speaker = _wire(tmp_path, state)

    bridge.export()
    spoken = announcer.tick()

    assert len(spoken) == 3
    # 高優先度 2 件 (blocker / approval) は割り込み付き
    assert speaker.interrupts == 2
    assert "ブロッカーです。認証フローの実装 が停止しました。外部依存の解決待ち" in spoken
    assert "承認待ちが発生しました。リリース可否の判断。確認をお願いします。" in spoken
    assert "設計ドキュメント整備 が完了しました。" in spoken


def test_second_tick_is_idempotent(tmp_path):
    state = MockOrgState()
    bridge, announcer, speaker = _wire(tmp_path, state)

    bridge.export()
    announcer.tick()
    before = list(speaker.utterances)

    bridge.export()  # 変化なし
    assert announcer.tick() == []
    assert speaker.utterances == before  # 二重読み上げなし


def test_low_priority_batched_when_many(tmp_path):
    items = [
        {"label": f"タスク{i}", "state": "completed"} for i in range(5)
    ]
    state = MockOrgState(items)
    bridge, announcer, speaker = _wire(tmp_path, state, batch_threshold=3)

    bridge.export()
    spoken = announcer.tick()

    # 5 件 > しきい値 3 → まとめ読み上げ 1 本に丸める
    assert spoken == ["更新が 5 件あります。完了 5 件、ブロッカー 0 件、承認待ち 0 件です。"]
    assert speaker.interrupts == 0


def test_state_transition_only_new_events(tmp_path):
    state = MockOrgState()
    bridge, announcer, speaker = _wire(tmp_path, state)
    bridge.export()
    announcer.tick()

    # ブロッカー解消 → 完了。新規イベント (completed) のみ読み上げ
    state.advance(
        [
            {"label": "設計ドキュメント整備", "state": "completed"},
            {"label": "認証フローの実装", "state": "completed"},
            {"label": "リリース可否の判断", "state": "approval_pending"},
        ]
    )
    bridge.export()
    spoken = announcer.tick()
    assert spoken == ["認証フローの実装 が完了しました。"]

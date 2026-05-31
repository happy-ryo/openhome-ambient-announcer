"""polling 基盤の冪等性テスト (docs/design.md §2.3 / §4.2 V-3)。"""

import json

from openhome_org_voice_core import EventPoller, OrgEvent, stable_event_id


def _write_events(path, events):
    payload = {"events": [e.to_dict() for e in events]}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _event(type_, subject):
    return OrgEvent(
        id=stable_event_id(type_, subject),
        type=type_,
        priority="normal",
        subject=subject,
        summary="",
        ts="2026-05-31T00:00:00Z",
    )


def test_missing_file_returns_empty(tmp_path):
    poller = EventPoller(tmp_path / "events.json")
    assert poller.poll_once() == []


def test_new_events_then_idempotent(tmp_path):
    events_path = tmp_path / "events.json"
    _write_events(events_path, [_event("task_completed", "A")])
    poller = EventPoller(events_path)

    first = poller.poll_once()
    assert [e.subject for e in first] == ["A"]

    # 同じ内容を再ポーリングしても二重読み上げしない (冪等)
    assert poller.poll_once() == []


def test_only_fresh_events_returned(tmp_path):
    events_path = tmp_path / "events.json"
    _write_events(events_path, [_event("task_completed", "A")])
    poller = EventPoller(events_path)
    poller.poll_once()

    # A は既読、B のみ新規
    _write_events(events_path, [_event("task_completed", "A"), _event("blocker_raised", "B")])
    fresh = poller.poll_once()
    assert [e.subject for e in fresh] == ["B"]


def test_seen_persists_across_restart(tmp_path):
    events_path = tmp_path / "events.json"
    seen_path = tmp_path / "seen.json"
    _write_events(events_path, [_event("task_completed", "A")])

    poller = EventPoller(events_path, seen_path)
    assert len(poller.poll_once()) == 1

    # 再起動を模して新しいインスタンスを作る → 既読集合が復元される
    restarted = EventPoller(events_path, seen_path)
    assert restarted.poll_once() == []

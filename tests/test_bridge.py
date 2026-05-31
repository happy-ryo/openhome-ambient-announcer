"""ブリッジの read-only / 原子的書き出し / public 衛生テスト (docs/design.md §2.2 / §6)。"""

import json

import pytest

from announcer.mock_state import MockOrgState, normalize
from openhome_org_voice_core import OrgEvent, StateBridge, stable_event_id
from openhome_org_voice_core.bridge import PublicHygieneError


def test_export_writes_normalized_json(tmp_path):
    state = MockOrgState()
    out = tmp_path / "events.json"
    bridge = StateBridge(state.snapshot, normalize, out)

    events = bridge.export()
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["events"]) == len(events) == 3
    types = {e["type"] for e in data["events"]}
    assert {"task_completed", "blocker_raised", "approval_pending"} == types


def test_bridge_does_not_mutate_state(tmp_path):
    state = MockOrgState()
    before = state.snapshot()
    bridge = StateBridge(state.snapshot, normalize, tmp_path / "events.json")
    bridge.export()
    assert state.snapshot() == before  # read-only 契約


def test_public_hygiene_blocks_absolute_path(tmp_path):
    def leaky(_snapshot):
        return [
            OrgEvent(
                id=stable_event_id("task_completed", "x"),
                type="task_completed",
                priority="normal",
                subject=r"C:\Users\secret\path",  # 絶対パスの漏れ
                summary="",
                ts="2026-05-31T00:00:00Z",
            )
        ]

    bridge = StateBridge(lambda: None, leaky, tmp_path / "events.json")
    with pytest.raises(PublicHygieneError):
        bridge.export()

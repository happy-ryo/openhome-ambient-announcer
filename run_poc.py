"""openhome-ambient-announcer M2 PoC ドライバ (ローカル完結).

組織 state(モック) → ブリッジ → 共有 JSON → polling → 発話(モック) の
一連の流れを 1 プロセスで回し、「読み上げるつもり」の発話文字列を stdout に出す。
OpenHome 実 API には繋がない (design §7 スコープ)。

実行: py -3 run_poc.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from announcer import AmbientAnnouncer
from announcer.mock_state import MockOrgState, normalize
from openhome_org_voice_core import EventPoller, MockSpeaker, StateBridge


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="ambient-announcer-poc-"))
    events_path = workdir / "events.json"
    seen_path = workdir / "seen.json"

    state = MockOrgState()
    bridge = StateBridge(state.snapshot, normalize, events_path)
    poller = EventPoller(events_path, seen_path)
    speaker = MockSpeaker(echo=False)
    announcer = AmbientAnnouncer(poller, speaker)

    print("=== openhome-ambient-announcer M2 PoC (mock / 一方向読み上げ) ===\n")

    # --- tick 1: 初期 state を読み上げ ---
    bridge.export()
    print("[tick 1] state をエクスポート → polling")
    _run_tick(announcer)

    # --- tick 2: 同じ state を再ポーリング (冪等: 二重読み上げしない) ---
    bridge.export()
    print("[tick 2] 変化なし → 既読のため発話なし (冪等性)")
    _run_tick(announcer)

    # --- tick 3: state が遷移 (ブロッカー解消 + マイルストン到達 + 着手) ---
    state.advance(
        [
            {"label": "設計ドキュメント整備", "state": "completed"},
            {"label": "認証フローの実装", "state": "completed"},  # 解消
            {"label": "リリース可否の判断", "state": "approval_pending"},
            {"label": "ロードマップ M2", "state": "milestone", "detail": "PoC scaffold 完了"},
            {"label": "コードレビュー対応", "state": "started"},
        ]
    )
    bridge.export()
    print("[tick 3] state 遷移 → 新規イベントのみ読み上げ")
    _run_tick(announcer)

    print(f"\n総発話数: {len(speaker.utterances)} / 割り込み: {speaker.interrupts}")


def _run_tick(announcer: AmbientAnnouncer) -> None:
    spoken = announcer.tick()
    if not spoken:
        print("  (発話なし)\n")
        return
    for line in spoken:
        print(f"  [speak] {line}")
    print()


if __name__ == "__main__":
    main()

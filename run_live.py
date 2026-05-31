"""openhome-ambient-announcer M3 ライブ実行ドライバ (実 OpenHome 接続).

組織 state(モック) → ブリッジ → 共有 JSON → polling → **実 OpenHome Cloud**
への WebSocket 発話 の end-to-end を 1 度通し、返ってきた合成音声を WAV として
保存する (実音声 end-to-end の証跡 — design §7 M3)。

M2 の run_poc.py との差分は **Speaker の実装だけ** (MockSpeaker →
OpenHomeWebSocketSpeaker)。bridge / poller / announcer / templates は共有のまま
で、設計どおり「どこに発話を出すか」だけが差し替わることを示す。

鍵の扱い (最重要・public リポ):
- OPENHOME_API_KEY は **環境変数からのみ** 取得する (os.environ)。
- 鍵をファイル・ログ・コミットに残さない。本スクリプトも鍵を一切出力しない。

実行 (bash):  OPENHOME_API_KEY=*** py -3 run_live.py
実行 (pwsh):  $env:OPENHOME_API_KEY="***"; py -3 run_live.py
"""

from __future__ import annotations

import os
from pathlib import Path

from announcer import AmbientAnnouncer
from announcer.mock_state import MockOrgState, normalize
from openhome_org_voice_core import (
    EventPoller,
    OpenHomeWebSocketSpeaker,
    StateBridge,
)

# 既定 agent (窓口決定: 開発用 Ori。個人 twin は使わない)
AGENT_ID = os.environ.get("OPENHOME_AGENT_ID", "587978")


def main() -> int:
    if not os.environ.get("OPENHOME_API_KEY"):
        print(
            "OPENHOME_API_KEY が未設定です。環境変数で渡してください:\n"
            "  bash : OPENHOME_API_KEY=*** py -3 run_live.py\n"
            "  pwsh : $env:OPENHOME_API_KEY=\"***\"; py -3 run_live.py"
        )
        return 2

    # var/ は .gitignore 済み (PoC ランタイム出力)。鍵も成果物も含めない。
    workdir = Path(__file__).resolve().parent / "var" / "live"
    workdir.mkdir(parents=True, exist_ok=True)
    events_path = workdir / "events.json"
    seen_path = workdir / "seen.json"
    audio_dir = workdir / "audio"

    state = MockOrgState()
    bridge = StateBridge(state.snapshot, normalize, events_path)
    poller = EventPoller(events_path, seen_path)
    speaker = OpenHomeWebSocketSpeaker(
        agent_id=AGENT_ID,
        audio_out_dir=audio_dir,
        echo=True,
    )
    announcer = AmbientAnnouncer(poller, speaker)

    print("=== openhome-ambient-announcer M3 LIVE (実 OpenHome Cloud / WebSocket) ===")
    print(f"agent_id={AGENT_ID}  audio_out={audio_dir}\n")

    try:
        bridge.export()  # state を read-only 参照 → 共有 JSON
        print("[tick] state をエクスポート → polling → 実 OpenHome へ発話")
        spoken = announcer.tick()
        for line in spoken:
            print(f"  [announce] {line}")
    finally:
        speaker.close()

    print("\n=== 受信サマリ (実音声 end-to-end 証跡) ===")
    total_bytes = 0
    for i, utt in enumerate(speaker.utterances):
        total_bytes += utt.audio_bytes
        print(
            f"  #{i:02d} sent={utt.text!r}\n"
            f"      frames={utt.audio_frames} bytes={utt.audio_bytes} "
            f"elapsed={utt.elapsed}s audio={utt.audio_path}\n"
            f"      agent応答(会話調)={utt.response!r}"
        )
    print(
        f"\n発話数={len(speaker.utterances)} 割り込み試行={speaker.interrupts} "
        f"受信音声合計={total_bytes} bytes"
    )
    ok = any(u.audio_bytes > 0 for u in speaker.utterances)
    print("RESULT:", "OK 実音声を受信" if ok else "NG 音声未受信 (要調査)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""polling → 発話整形 → speak の結線と二段の流量制御 (docs/design.md §2.3 / §3.3).

AmbientAnnouncer は Background Ability の本体ロジックに相当する。
M2 では OpenHome ランタイムには載せず、純ロジックとして tick() を回して検証する。

流量制御 (design §3.3 の二段):
1. 高優先度 (blocker / approval_pending) は send_interrupt_signal() で即時割り込み・個別読み上げ。
2. それ以外は、同時多発時はバッチ要約に丸め、少数なら個別読み上げ。
"""

from __future__ import annotations

from openhome_org_voice_core import EventPoller, OrgEvent, Speaker

from .templates import HIGH_PRIORITY_TYPES, render_batch, render_event


class AmbientAnnouncer:
    """共有 JSON を polling し、組織状況を一方向に読み上げる。"""

    def __init__(
        self,
        poller: EventPoller,
        speaker: Speaker,
        *,
        batch_threshold: int = 3,
    ) -> None:
        self._poller = poller
        self._speaker = speaker
        self._batch_threshold = batch_threshold

    def tick(self) -> list[str]:
        """1 ポーリング周期分を処理し、読み上げた文字列の一覧を返す。"""
        fresh = self._poller.poll_once()
        if not fresh:
            return []

        spoken: list[str] = []
        high = [e for e in fresh if e.type in HIGH_PRIORITY_TYPES]
        rest = [e for e in fresh if e.type not in HIGH_PRIORITY_TYPES]

        # 1) 高優先度: 即時割り込み・個別読み上げ
        for ev in high:
            self._speaker.send_interrupt_signal()
            spoken.append(self._say(ev))

        # 2) それ以外: 多発時はまとめ読み上げ、少数なら個別
        if len(rest) > self._batch_threshold:
            text = render_batch(rest)
            self._speaker.speak(text)
            spoken.append(text)
        else:
            for ev in rest:
                spoken.append(self._say(ev))

        return spoken

    def _say(self, event: OrgEvent) -> str:
        text = render_event(event)
        self._speaker.speak(text)
        return text

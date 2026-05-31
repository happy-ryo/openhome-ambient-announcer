"""発話 I/F とモック実装 (docs/design.md §4.1 / §4.4).

OpenHome SDK の `send_interrupt_signal()` → `speak()` を抽象化する。
M2 では実 API には繋がず (design §7 / スコープ)、MockSpeaker が発話文字列を
記録・出力するだけに留める。

**一方向の担保 (design §4.4)**: Speaker は読み上げ専用。
`user_response()` / `run_confirmation_loop()` / `start_audio_recording()` 等の
入力系メソッドは **定義しない**。組織へ書き戻す経路も持たない。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Speaker(ABC):
    """OpenHome 発話 I/F (出力のみ)。"""

    @abstractmethod
    def send_interrupt_signal(self) -> None:
        """出力中の発話を中断する (高優先度の即時割り込み — design §3.3)。"""

    @abstractmethod
    def speak(self, text: str) -> None:
        """text を能動的に読み上げる。"""


class MockSpeaker(Speaker):
    """発話を実行せず、文字列として記録/出力するモック (M2 PoC)。"""

    def __init__(self, *, echo: bool = False) -> None:
        self.utterances: list[str] = []
        self.interrupts: int = 0
        self._echo = echo

    def send_interrupt_signal(self) -> None:
        self.interrupts += 1
        if self._echo:
            print("[interrupt]")

    def speak(self, text: str) -> None:
        self.utterances.append(text)
        if self._echo:
            print(f"[speak] {text}")

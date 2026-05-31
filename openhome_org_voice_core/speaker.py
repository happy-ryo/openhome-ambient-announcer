"""発話 I/F・モック・実 OpenHome 接続 (docs/design.md §4.1 / §4.4).

`Speaker` は発話 I/F の抽象。実装は 2 系統:
- `MockSpeaker` … 発話文字列を記録するだけ (単体テスト用。M2 から存置)。
- `OpenHomeWebSocketSpeaker` … M3 実接続。OpenHome Cloud の WebSocket
  voice-stream にテキストを送り、返ってきた合成音声 (PCM) を受信する。

**M3 実測メモ (design §4 の ≈ 検証点を実 API で確定)**:
M1 設計が想定した「クラウド常駐 Background Ability 内の verbatim `speak()` /
`send_interrupt_signal()`」は **cloud API キー単独では到達できない経路**だった
(REST API は agent/ability 管理専用で TTS 終端なし、音声出力の実経路は WebSocket
のみ)。本実装は cloud キーで実到達できる WebSocket 経路に音声機構を移す。
詳細は docs/design.md §4.1 / §4.2 を参照。

**一方向の担保 (design §4.4)**: Speaker は読み上げ (出力) 専用。
`user_response()` / `run_confirmation_loop()` / `start_audio_recording()` 等の
入力系メソッドは **定義しない**。組織へ書き戻す経路も持たない。
WebSocket 実装もテキスト送信 → 音声受信の一方向のみで、マイク入力・返答
キャプチャ・組織への書き戻しは行わない。
"""

from __future__ import annotations

import base64
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# OpenHome Cloud WebSocket voice-stream (実測で確定 — design §4.1)
OPENHOME_WS_BASE = "wss://app.openhome.com/websocket/voice-stream"
OPENHOME_ORIGIN = "https://app.openhome.com"
# 既定の開発用 agent "Ori" (窓口決定: 個人 twin は使わない)
DEFAULT_AGENT_ID = "587978"

# **実測で確定した重要点 (design §4.2 V-2 系)**:
# OpenHome のエッジ/WAF は websockets ライブラリ既定の User-Agent を弾き、
# どのメッセージでも即 `1008 policy violation` で切断する。ブラウザ風の
# User-Agent を付けるとハンドシェイク後のセッションが確立し音声が返る。
# (Origin だけでは不十分で、User-Agent が決定的だった。)
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 受信音声は ElevenLabs 由来の **MP3** (ID3/Lavf) で返る (実測)。
# 16-bit PCM / 16kHz は *クライアント→サーバ* のマイク音声仕様であり、
# *サーバ→クライアント* の合成音声は MP3。よって受信音声は .mp3 で保存する。
RECV_AUDIO_EXT = ".mp3"


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


@dataclass
class Utterance:
    """1 発話分の往復記録 (実測・証跡用)。"""

    text: str                      # 送信したアナウンス文
    response: str = ""             # agent が返した会話応答テキスト (会話調・非逐語)
    audio_frames: int = 0          # 受信した audio フレーム数
    audio_bytes: int = 0           # 受信した音声バイト数 (MP3)
    audio_path: str | None = None  # 保存先 MP3 (実音声 end-to-end の証跡)
    elapsed: float = 0.0           # 送信→受信完了までの実測秒 (レイテンシ — design §4.2 V-4)


class OpenHomeWebSocketSpeaker(Speaker):
    """OpenHome Cloud の WebSocket voice-stream に接続する実 Speaker (M3).

    `speak(text)` は text をユーザ発話 (`{"type":"transcribed","data":text}`) として
    送り、agent が返す合成音声フレーム (`type:"audio"`, base64 **MP3**) と応答テキストを
    受信する。受信音声は MP3 として保存でき、実音声 end-to-end の証跡になる。
    通話シーケンスの詳細は `speak()` の docstring と design §4.5 を参照。

    会話調 (非逐語) の応答になる点・割り込み API 相当が無い点・接続にブラウザ風
    User-Agent ヘッダが必須な点は M3 実測で確定した実 API の制約 (design §4.5)。

    鍵 (api_key) は URL 構築にのみ用い、ログ・例外メッセージへ出さない。
    既定では os.environ['OPENHOME_API_KEY'] から読む (コードにハードコードしない)。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        agent_id: str = DEFAULT_AGENT_ID,
        audio_out_dir: str | os.PathLike | None = None,
        idle_timeout: float = 5.0,
        max_wait: float = 40.0,
        echo: bool = False,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("OPENHOME_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENHOME_API_KEY が未設定です。環境変数で渡してください "
                "(コードにハードコードしない — design 鍵の扱い)。"
            )
        self._key = key
        self._agent_id = str(agent_id)
        self._audio_out_dir = Path(audio_out_dir) if audio_out_dir else None
        self._idle_timeout = idle_timeout
        self._max_wait = max_wait
        self._echo = echo
        self._ws = None
        self.interrupts: int = 0
        self.utterances: list[Utterance] = []

    # --- 接続管理 -------------------------------------------------------
    def _url(self) -> str:
        # 鍵は URL path に入る。例外・ログには出さない。
        return f"{OPENHOME_WS_BASE}/{self._key}/{self._agent_id}"

    def connect(self) -> None:
        if self._ws is not None:
            return
        # websockets は実接続時のみ必要 (単体テストの MockSpeaker では不要)
        from websockets.sync.client import connect

        # ブラウザ風 User-Agent が必須 (実測: 既定 UA だと 1008 で即切断 — 上記注記)
        self._ws = connect(
            self._url(),
            max_size=None,
            open_timeout=20,
            additional_headers={
                "User-Agent": _BROWSER_USER_AGENT,
                "Origin": OPENHOME_ORIGIN,
            },
        )

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None

    def __enter__(self) -> "OpenHomeWebSocketSpeaker":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- Speaker I/F (出力のみ) ----------------------------------------
    def send_interrupt_signal(self) -> None:
        """高優先度の即時割り込み。

        M3 実測: cloud WebSocket 経路には docs 上の割り込み終端が無い
        (design §4.2 V-2)。verbatim な `send_interrupt_signal()` は DevKit /
        ランタイム内 Ability 側の機能であり、cloud キー単独では到達できない。
        ここでは回数のみ記録する best-effort no-op とし、実挙動は design.md に明記。
        """
        self.interrupts += 1
        if self._echo:
            print("[interrupt] (cloud WS 経路では no-op / DevKit 側機能)")

    def speak(self, text: str) -> Utterance:
        """text を組織イベントの発話として送り、agent の応答音声 (MP3) を受信・保存する。

        **実測で確定した通話シーケンス (design §4.5)**:
        通話開始時に agent はまず cold_start の挨拶を発話する (turn 0)。挨拶の
        `audio-end` を待ってから `{"type":"transcribed","data":text}` でイベント文を
        ユーザ発話として送ると、agent がその内容に対する応答を発話する (turn 1)。
        本メソッドは **turn 1 (応答) の音声**を保存する (turn 0 の挨拶は捨てる)。
        挨拶中にイベント文を送ると無視されるため、必ず挨拶完了後に送る。
        """
        # 1 アナウンス = 1 通話。毎回新規接続で前通話の状態を持ち越さない。
        self.close()
        self.connect()
        assert self._ws is not None
        ws = self._ws

        start = time.monotonic()
        audio = bytearray()      # turn 1 (応答) の音声のみ
        frames = 0
        response_parts: list[str] = []
        greeting_done = False    # turn 0 (挨拶) の audio-end を受信したか
        sent = False             # イベント文 (transcribed) を送信したか
        deadline = start + self._max_wait

        def _send_event() -> None:
            nonlocal sent
            ws.send(json.dumps({"type": "transcribed", "data": text}))
            sent = True

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                raw = ws.recv(timeout=min(self._idle_timeout, max(remaining, 0.1)))
            except TimeoutError:
                if sent and frames > 0:
                    break  # 応答音声を受信済の無音 = 応答完了
                # 挨拶 audio-end を取りこぼした場合の保険: 一定経過で送信
                if not sent and time.monotonic() - start > 10:
                    greeting_done = True
                    _send_event()
                continue

            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", "replace")
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")
            if mtype == "audio":
                if sent:  # turn 1 (応答) のみ収集。turn 0 の挨拶音声は捨てる
                    chunk = base64.b64decode(msg.get("data", "") or "")
                    if chunk:
                        audio += chunk
                        frames += 1
            elif mtype == "message":
                data = msg.get("data") or {}
                # 送信後の assistant 応答 (= イベント文への返答) のみ拾う
                if sent and isinstance(data, dict) and data.get("role") == "assistant":
                    content = data.get("content")
                    if content:
                        response_parts.append(str(content))
            elif mtype == "text":
                d = msg.get("data")
                if d == "audio-end":
                    if not greeting_done:
                        # turn 0 (挨拶) 完了 → イベント文を送る
                        greeting_done = True
                        _send_event()
                    elif sent and frames > 0:
                        # turn 1 (応答) 完了 → 1 アナウンス分を確定し終了
                        break

        elapsed = time.monotonic() - start
        utt = Utterance(
            text=text,
            response=response_parts[-1] if response_parts else "",
            audio_frames=frames,
            audio_bytes=len(audio),
            elapsed=round(elapsed, 2),
        )
        if audio and self._audio_out_dir is not None:
            utt.audio_path = self._write_audio(bytes(audio), len(self.utterances))
        self.utterances.append(utt)
        self.close()  # 通話終了。次の発話は新規接続で開始する。

        if self._echo:
            print(
                f"[speak] sent={text!r} | frames={frames} bytes={len(audio)} "
                f"elapsed={elapsed:.1f}s audio={utt.audio_path}"
            )
        return utt

    # --- 証跡 音声書き出し (MP3) ---------------------------------------
    def _write_audio(self, audio: bytes, index: int) -> str:
        self._audio_out_dir.mkdir(parents=True, exist_ok=True)
        path = self._audio_out_dir / f"announce-{index:02d}{RECV_AUDIO_EXT}"
        with open(path, "wb") as fh:
            fh.write(audio)  # ElevenLabs 由来 MP3 をそのまま保存
        return str(path)

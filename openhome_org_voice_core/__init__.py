"""openhome-org-voice-core — 組織 state を OpenHome へ橋渡しする共有中核 (M2 PoC).

姉妹プロジェクト openhome-ambient-announcer / openhome-approval-voice が
共有する中核機構。docs/design.md §5 の共有コンポーネントに対応する。

- envelope: 正規化イベント・エンベロープ (design §3.2)
- bridge:   組織 state → 正規化イベント JSON ブリッジ (read-only, design §2.2)
- poller:   共有 JSON の polling + 既読集合による冪等読み上げ基盤 (design §2.3)
- speaker:  発話 I/F とモック実装 (一方向: 読み上げのみ, design §4.4)

本パッケージは「どのイベントを拾い、どう読み上げるか」を含まない。
それはプロジェクト固有部分 (design §5.2) であり、各プロジェクト側で実装する。
"""

from .envelope import EVENT_TYPES, PRIORITIES, OrgEvent, stable_event_id
from .bridge import StateBridge
from .poller import EventPoller
from .speaker import MockSpeaker, Speaker

__all__ = [
    "OrgEvent",
    "EVENT_TYPES",
    "PRIORITIES",
    "stable_event_id",
    "StateBridge",
    "EventPoller",
    "Speaker",
    "MockSpeaker",
]

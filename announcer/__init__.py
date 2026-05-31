"""openhome-ambient-announcer — プロジェクト固有部分 (docs/design.md §5.2).

共有中核 (openhome_org_voice_core) の上に、本件固有の
「どのイベントを拾い、どう読み上げるか」を載せる。

- templates: 一般イベントの発話テンプレート (design §3.3)
- app:       polling → 発話整形 → speak の結線と流量制御 (design §2.3 / §3.3)
- mock_state: PoC 用の public-safe な組織 state スタブ (design §6 / §7 M2)
"""

from .app import AmbientAnnouncer
from .templates import render_batch, render_event

__all__ = ["AmbientAnnouncer", "render_event", "render_batch"]

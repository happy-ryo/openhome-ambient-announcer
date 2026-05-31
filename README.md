# openhome-ambient-announcer

OpenHome 常駐 Ability で claude-org マルチエージェント組織の状況（完了・ブロッカー・承認待ち等）を
**音声で能動アナウンス**する一方向連携。OpenHome DevKit 連携チャレンジ。

> 一方向: **OpenHome → 人間の読み上げのみ**。音声入力・操作・承認応答の経路は持たない（[設計 §1.3 / §4.4](docs/design.md)）。

- M1: 設計・技術調査 → [`docs/design.md`](docs/design.md)
- M2: PoC scaffold（モック）— ローカル完結。OpenHome 実 API には繋がない。
- **M3 (本マイルストン): 実接続** — cloud API キー経由で OpenHome の WebSocket voice-stream に接続し、
  組織イベント → 実音声アナウンス（MP3）の end-to-end を通過。レイテンシ実測。
  実測仕様は [設計 §4.5](docs/design.md) に反映。

## スコープ

組織 state（モック）→ ブリッジ → 共有イベント JSON → polling（差分検知）→ `Speaker` の
一連の流れをローカル 1 プロセスで再現する。`Speaker` 実装だけが差し替わる:
- **M2**: `MockSpeaker`（発話文字列を記録するだけ・単体テスト用）。
- **M3**: `OpenHomeWebSocketSpeaker`（実 OpenHome Cloud に接続し、実音声 MP3 を受信）。

## 構成

```
openhome_org_voice_core/   # 姉妹プロジェクトと共有する中核 (設計 §5)
  envelope.py              #   正規化イベント・エンベロープ (設計 §3.2)
  bridge.py                #   state → 正規化イベント JSON ブリッジ (read-only, 原子的書き出し)
  poller.py                #   polling + 既読集合による冪等読み上げ基盤
  speaker.py               #   発話 I/F・モック・実 OpenHome 接続 (出力のみ)
announcer/                 # 本件固有部分 (設計 §5.2)
  templates.py             #   一般イベントの発話テンプレート (設計 §3.3)
  app.py                   #   結線と二段の流量制御 (高優先=即時割り込み / 多発=バッチ要約)
  mock_state.py            #   public-safe な組織 state スタブ + normalizer
run_poc.py                 # M2 PoC ドライバ (モック・ローカル完結)
run_live.py                # M3 ライブドライバ (実 OpenHome 接続・実音声 MP3 を保存)
tests/                     # 発話文面の固定・冪等性・流量制御の単体テスト
```

`openhome_org_voice_core` は姉妹プロジェクト **openhome-approval-voice** と共有する中核機構の
契約（[設計 §3.2 エンベロープ / §5 共有コンポーネント](docs/design.md)）に準拠する。
「どのイベントを拾い、どう読み上げるか」のみが `announcer/` 側のプロジェクト固有部分。

## 実行

```bash
# M2 PoC（モック・ローカル完結。発話文字列を stdout に出力）
py -3 run_poc.py

# 単体テスト
py -3 -m pytest

# M3 ライブ（実 OpenHome 接続。実音声 MP3 を var/live/audio/ に保存）
#   依存: py -3 -m pip install websockets
#   鍵は環境変数で前置（コミット/ログ/設定ファイルに残さない）
OPENHOME_API_KEY=*** py -3 run_live.py          # bash
$env:OPENHOME_API_KEY="***"; py -3 run_live.py  # PowerShell
```

> Windows では `python` ではなく `py -3` を使用してください。

### M3 ライブ接続メモ（実測）

- 接続先: `wss://app.openhome.com/websocket/voice-stream/{OPENHOME_API_KEY}/{AGENT_ID}`
- **鍵は環境変数 `OPENHOME_API_KEY` からのみ取得**。コード・設定・ログ・コミットに残さない（public リポ）。
- クライアントは **ブラウザ風 `User-Agent`** ヘッダ必須。無いと OpenHome のエッジに弾かれ
  `1008 policy violation` で即切断される（実測でハマった点）。
- テキスト送信形式は `{"type":"transcribed","data":"<text>"}`。接続後 agent はまず挨拶を発話し、
  その完了後にイベント文を送ると内容に応じた応答を発話する（応答音声 = **MP3**/ElevenLabs を保存）。
  詳細は [設計 §4.5](docs/design.md)。

## 設計上の境界（M2 で守ること）

- 一方向のみ。`Speaker` は読み上げ専用で入力系メソッドを持たない（設計 §4.4）。
- ブリッジは state を read-only で参照し、書き戻さない（設計 §1.3）。
- public 衛生: 絶対パス・内部フック名・state スキーマの生写し・内部 ID 生値を出力に含めない（設計 §6）。
  ブリッジが抽象化の単一関門となり、漏れを検出する。

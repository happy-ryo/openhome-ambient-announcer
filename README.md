# openhome-ambient-announcer

OpenHome 常駐 Ability で claude-org マルチエージェント組織の状況（完了・ブロッカー・承認待ち等）を
**音声で能動アナウンス**する一方向連携。OpenHome DevKit 連携チャレンジ。

> 一方向: **OpenHome → 人間の読み上げのみ**。音声入力・操作・承認応答の経路は持たない（[設計 §1.3 / §4.4](docs/design.md)）。

- M1: 設計・技術調査 → [`docs/design.md`](docs/design.md)
- **M2 (本マイルストン): PoC scaffold（モック）** — ローカル完結。OpenHome 実 API には繋がない。
- M3: 実接続（組織 state 実エクスポータ・レイテンシ実測・DevKit 実機）

## M2 のスコープ

組織 state（モック）→ ブリッジ → 共有イベント JSON → polling（差分検知）→ `speak()`（モック）の
一連の流れをローカル 1 プロセスで再現し、「読み上げるつもり」の発話文字列を出力する。

## 構成

```
openhome_org_voice_core/   # 姉妹プロジェクトと共有する中核 (設計 §5)
  envelope.py              #   正規化イベント・エンベロープ (設計 §3.2)
  bridge.py                #   state → 正規化イベント JSON ブリッジ (read-only, 原子的書き出し)
  poller.py                #   polling + 既読集合による冪等読み上げ基盤
  speaker.py               #   発話 I/F とモック実装 (出力のみ)
announcer/                 # 本件固有部分 (設計 §5.2)
  templates.py             #   一般イベントの発話テンプレート (設計 §3.3)
  app.py                   #   結線と二段の流量制御 (高優先=即時割り込み / 多発=バッチ要約)
  mock_state.py            #   public-safe な組織 state スタブ + normalizer
run_poc.py                 # PoC ドライバ
tests/                     # 発話文面の固定・冪等性・流量制御の単体テスト
```

`openhome_org_voice_core` は姉妹プロジェクト **openhome-approval-voice** と共有する中核機構の
契約（[設計 §3.2 エンベロープ / §5 共有コンポーネント](docs/design.md)）に準拠する。
「どのイベントを拾い、どう読み上げるか」のみが `announcer/` 側のプロジェクト固有部分。

## 実行

```bash
# PoC を実行（発話文字列を stdout に出力）
py -3 run_poc.py

# 単体テスト
py -3 -m pytest
```

> Windows では `python` ではなく `py -3` を使用してください。

## 設計上の境界（M2 で守ること）

- 一方向のみ。`Speaker` は読み上げ専用で入力系メソッドを持たない（設計 §4.4）。
- ブリッジは state を read-only で参照し、書き戻さない（設計 §1.3）。
- public 衛生: 絶対パス・内部フック名・state スキーマの生写し・内部 ID 生値を出力に含めない（設計 §6）。
  ブリッジが抽象化の単一関門となり、漏れを検出する。

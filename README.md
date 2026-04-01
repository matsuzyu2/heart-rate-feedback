# Heart-Rate Biofeedback（リビルド版）

本リポジトリは、大学院研究向けに再構築中の HRFB（心拍バイオフィードバック）実装です。
スコープは HRFB 関連機能に限定しています。

- Polar H10 からの ECG ストリーミング
- ECG 信号処理と R 波ベースの心拍推定
- 視覚フィードバック GUI
- EEG トリガー送信（ActiCHamp / Cognionics / LSL）
- 縦断セッション向けの構造化ロギング

## 現在の実装状況

初期基盤の実装は完了しています。

- 新アーキテクチャの主要モジュールを追加（config/gui/logging/sensor/trigger/session）
- 聴覚フィードバック関連を削除
- トリガーディスパッチ基盤を追加（共通タイムスタンプ＋並列送信）
- 参加者永続化とセッション履歴参照を実装
- 初期テストを追加し、通過を確認

## セットアップ

```bash
python3 -m pip install -r requirements.txt
```

## 起動

```bash
python3 -m src.main
```

## 日次統合チェック（Ticket 7）

作業終了前に、以下を実行してください。

```bash
bash scripts/daily_mvp_check.sh
```

このスクリプトで次を検証します。

- MVP 自動テスト
- セッションメタデータのライフサイクル保存（書き込み/読み出し）
- 一時データディレクトリでのトリガーログ生成

GUI は手動確認が必要です。

1. アプリを起動する（`python3 -m src.main`）
2. テスト参加者でセッションを開始する
3. フェーズ自動進行と Next Phase 動作を確認する
4. `data/` 配下に `session_meta.json` と `trigger_log.csv` が更新されることを確認する

## データ構成（目標）

セッションデータは次の構成で保存されます。

- `data/Pxxx/participant.json`
- `data/Pxxx/session_yyy/session_meta.json`
- `data/Pxxx/session_yyy/ecg_raw.csv`
- `data/Pxxx/session_yyy/heartbeats.csv`
- `data/Pxxx/session_yyy/feedback_events.csv`
- `data/Pxxx/session_yyy/trigger_log.csv`

## 補足

- 旧実装から新実装への移行途中です。
- BLE ストリーミングの完全接続とセッション統合制御は継続実装中です。



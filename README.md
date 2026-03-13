# Heart Rate Feedback
卒業研究用に、BFと安静時心拍の取得とトリガー送信を一挙にまとめたコード

## セットアップ

### Windows

#### 1. 仮想環境の作成
```powershell
python -m venv .venv
```

#### 2. 仮想環境の有効化に必要な設定
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 3. 仮想環境の有効化
```powershell
.\.venv\Scripts\Activate.ps1
```

#### 4. 依存関係のインストール
```powershell
pip install -r requirements.txt
```

### Mac / Linux

#### 1. 仮想環境の作成
```bash
python3 -m venv .venv
```

#### 2. 仮想環境の有効化
```bash
source .venv/bin/activate
```

#### 3. 依存関係のインストール
```bash
pip install -r requirements.txt
```

## 実行方法

### Windows
```powershell
# 仮想環境を有効化してから実行

# 心拍数減少モード
python src/ecg_main.py --mode decrease

# ランダム
python src/ecg_main.py --mode random

# 心拍数増加モード
python src/ecg_main.py --mode increase
```

### Mac / Linux
```bash
# 仮想環境を有効化してから実行

# 心拍数減少モード
python3 src/ecg_main.py --mode decrease

# ランダム
python3 src/ecg_main.py --mode random

# 心拍数増加モード
python3 src/ecg_main.py --mode increase
```

## ディレクトリ構成

```
heart-rate-feedback/
├── src/                          # ソースコード
│   ├── ecg_main.py              # メインエントリーポイント（実行ファイル）
│   ├── config/                  # 設定関連
│   │   └── ecg_config.py       # ECG処理とシステム全体の設定パラメータ
│   ├── feedback/                # フィードバック制御
│   │   ├── audio_feedback.py   # オーディオフィードバックの再生制御
│   │   └── feedback_modes.py   # フィードバックモード（増加/減少/ランダム）の定義
│   ├── logger/                  # データロギング
│   │   ├── base_logger.py      # ロガーの基底クラス
│   │   ├── actichamp_trigger_logger.py  # ActiCHampトリガーログ記録
│   │   ├── beat_event_logger.py         # 心拍イベントログ記録
│   │   ├── cognio_trigger_logger.py     # Cognioトリガーログ記録
│   │   ├── ecg_logger.py                # ECG生データログ記録
│   │   ├── feedback_event_logger.py     # フィードバックイベントログ記録
│   │   └── instantaneous_hr_logger.py   # 瞬時心拍数ログ記録
│   ├── processing/              # 信号処理
│   │   ├── ecg_processor.py              # ECG信号の前処理とフィルタリング
│   │   ├── simple_r_peak_detector.py     # R-peak検出アルゴリズム
│   │   └── instantaneous_heart_rate.py   # 瞬時心拍数計算
│   ├── sensor/                  # センサー通信
│   │   ├── ecg_interface.py           # Polar H10センサーとのBLE通信インターフェース
│   │   ├── actichamp_trigger.py       # ActiCHampトリガー送信（シリアル通信）
│   │   ├── cognio_trigger.py          # Cognioトリガー送信（ZMQ通信）
│   │   └── lsl_outlet.py              # Lab Streaming Layer出力
│   └── session/                 # セッション管理
│       └── ecg_session_controller.py  # セッション全体の制御とオーケストレーション
│
├── assets/                      # アセットファイル
│   └── audio/                   # オーディオファイル
│       ├── high_sound.wav      # 高音フィードバック音（心拍数増加時）
│       └── low_sound.wav       # 低音フィードバック音（心拍数減少時）
│
├── logs/                        # ログファイル保存先
│   ├── actichamp_trigger/      # ActiCHampトリガーのタイムスタンプログ
│   ├── beat/                   # 心拍イベント（R-peak検出）のログ
│   ├── cognio_trigger/         # Cognioトリガーのタイムスタンプログ
│   ├── ecg/                    # ECG生データのログ
│   ├── feedback_event/         # フィードバックイベントのログ
│   └── instantaneous_hr/       # 瞬時心拍数のログ
│
├── requirements.txt             # Python依存パッケージリスト
├── pyproject.toml              # プロジェクト設定ファイル
├── LICENSE                     # ライセンスファイル
└── README.md                   # このファイル
```

### 主要コンポーネントの説明

#### センサー系 (src/sensor/)
- **ecg_interface.py**: Polar H10心拍センサーからBluetooth経由でECGデータを取得
- **actichamp_trigger.py**: ActiCHamp脳波計にシリアル経由でトリガー信号を送信
- **cognio_trigger.py**: Cognioシステムに心拍イベントを通知
- **lsl_outlet.py**: Lab Streaming Layerプロトコルでデータをストリーミング

#### 信号処理系 (src/processing/)
- **ecg_processor.py**: バンドパスフィルタによるECG信号のノイズ除去
- **simple_r_peak_detector.py**: リアルタイムR-peak（心拍）検出
- **instantaneous_heart_rate.py**: RR間隔から瞬時心拍数を計算

#### フィードバック系 (src/feedback/)
- **audio_feedback.py**: pygameを使用した音声フィードバックの再生
- **feedback_modes.py**: 3種類のフィードバックモード（increase/decrease/random）

#### ロギング系 (src/logger/)
- すべてのセンサーデータ、処理結果、イベントをタイムスタンプ付きでCSV形式で保存
- セッションごとに独立したログファイルを生成

#### セッション管理 (src/session/)
- **ecg_session_controller.py**: 全コンポーネントを統合し、実験セッション全体を制御

## 主な依存関係

- **bleak**: Bluetooth Low Energy通信（Polar H10センサー接続用）
- **pygame**: オーディオフィードバック再生
- **numpy**: 信号処理（R-peak検出アルゴリズム）
- **pyzmq**: Cognioトリガー通信
- **pyserial**: シリアル通信



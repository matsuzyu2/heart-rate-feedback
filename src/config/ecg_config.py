# ECG専用設定ファイル

# =============================================================================
#                   Polarに関する設定
# =============================================================================
# Polarデバイス設定
ECG_POLAR_DEVICE_ID = "D1948025" # Polar H10のデバイスID（例: D1948025）をそのまま記載

# ECG Service UUID（Polar独自）
ECG_SERVICE_UUID = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
ECG_CONTROL_POINT_UUID = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"  # PMD Control（コマンド送信用）
ECG_DATA_UUID = "fb005c82-02e7-f387-1cad-8acd2d8df0c8"  # PMD Data（データ受信用）

# =============================================================================
#                   ECGデータ取得に関する設定
# =============================================================================
# ECGデータ取得設定
ECG_SAMPLING_RATE = 130
ECG_TIMEOUT_SECONDS = 30

# データ記録設定
ECG_LOG_DIRECTORY = "logs/ecg"
BEAT_LOG_DIRECTORY = "logs/beat"
INSTANTANEOUS_HR_LOG_DIRECTORY = "logs/instantaneous_hr"
FEEDBACK_EVENT_LOG_DIRECTORY = "logs/feedback_event"
COGNIO_TRIGGER_LOG_DIRECTORY = "logs/cognio_trigger"

# 心拍数解析設定
HR_TREND_THRESHOLD_BPM = 1.0  # トレンド判定の閾値（BPM）
HR_BLOCK_WINDOW_SECONDS = 5.0  # ブロック平均の時間窓（秒）
HR_FILTER_THRESHOLD_BPM = 10.0  # 瞬間心拍数フィルタリングの閾値（BPM）

# 過渡応答除外設定
TRANSITION_PERIOD_SECONDS = 10.0  # Polarセンサー装着時の過渡応答期間（秒）

# セッション自動終了設定
SESSION_DURATION_SECONDS = 900  # 実験時間（秒）

# ランダムモード設定
RANDOM_MODE_WEIGHTS = {
    'high': 0.33,   # high音の出力割合
    'low': 0.36,    # low音の出力割合
    'stable': 0.31  # stable(音なし)の出力割合
}  # 注意: 合計が1.0になるように調整してください

# ランダムモードの総フィードバック回数
RANDOM_MODE_TOTAL_FEEDBACKS = int(SESSION_DURATION_SECONDS / HR_BLOCK_WINDOW_SECONDS)

# =============================================================================
#                         トリガー送信に関する設定
# =============================================================================

# Cognioトリガー設定
ENABLE_COGNIO_TRIGGER = False  # Cognioトリガー機能の有効/無効
COGNIO_ZMQ_ADDRESS = "tcp://127.0.0.1:50000"  # ZMQ通信アドレス
COGNIO_SERIAL_PORT = "COM10"  # シリアルポート（Windows: COM1, COM3等、macOS: /dev/tty.usbserial）
COGNIO_SERIAL_BAUDRATE = 9600  # シリアル通信速度

# Cognioトリガーコード
COGNIO_TRIGGER = 100


# actiCHampトリガー設定
ENABLE_ACTICHAMP_TRIGGER = False  # actiCHampトリガー機能の有効/無効
ACTICHAMP_SERIAL_PORT = "COM4"  # シリアルポート（Windows: COM1, COM3等、macOS: /dev/tty.usbserial）
ACTICHAMP_SERIAL_BAUDRATE = 2000000  # シリアル通信速度
ACTICHAMP_TRIGGER_LOG_DIRECTORY = "logs/actichamp_trigger"

# actiCHampトリガーコード
ACTICHAMP_TRIGGER = 1

# LSL (Lab Streaming Layer) 設定
ENABLE_LSL = False  # LSL機能の有効/無効
LSL_STREAM_NAME = "HR_feedback_VScode"  # ストリーム名
LSL_STREAM_TYPE = "Markers"  # ストリームタイプ
LSL_SOURCE_ID = "hr_feedback_marker"  # ソースID（一意の識別子）

# LSLトリガーコード
LSL_TRIGGER_SESSION_START = 100      # セッション開始
LSL_TRIGGER_SESSION_STOP = 200      # セッション終了
LSL_TRIGGER_FEEDBACK_HIGH = 1000  # 心拍数上昇フィードバック
LSL_TRIGGER_FEEDBACK_LOW = 2000  # 心拍数下降フィードバック


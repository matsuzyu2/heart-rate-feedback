# ECG専用Polarインターフェース
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
import logging
from typing import Callable, Optional, TypedDict

# ECG専用設定を読み込み
from ..config.ecg_config import (
    ECG_POLAR_DEVICE_ID,
    ECG_SERVICE_UUID,
    ECG_CONTROL_POINT_UUID,
    ECG_DATA_UUID,
    ECG_TIMEOUT_SECONDS,
    TRANSITION_PERIOD_SECONDS
)

# ログ設定
# DEBUG: basicConfigをコメントアウト（ecg_main.pyの設定を使用）
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ECGDataResult(TypedDict):
    """ECGデータ解析結果の型定義"""
    ecg_samples: list[int]
    timestamps: list[int]


# ECGデータを受信した際に呼び出されるコールバック関数の型エイリアス。
# 解析済みのECGデータ（ECGDataResult型）を引数として受け取り、戻り値はNone。
ECGCallback = Callable[[ECGDataResult], None]


class ECGDataFormatter:
    """
    ECG生データの変換専用クラス
    """
    
    def __init__(self) -> None:
        """ECGDataFormatterを初期化"""
        pass
    
    def convert_array_to_signed_int(self, data: bytes, offset: int, length: int) -> int:
        """バイト配列を符号付き整数に変換"""
        return int.from_bytes(
            bytearray(data[offset : offset + length]), byteorder="little", signed=True,
        )

    def convert_to_unsigned_long(self, data: bytes, offset: int, length: int) -> int:
        """バイト配列を符号なし長整数に変換"""
        return int.from_bytes(
            bytearray(data[offset : offset + length]), byteorder="little", signed=False,
        )  
    
    def parse_ecg_data(self, raw_data: bytes) -> ECGDataResult:
        """
        Polarセンサーからの生ECGデータを解析
        
        Args:
            raw_data (bytes): Polarセンサーからの生ECGデータ
            
        Returns:
            ECGDataResult: ECGサンプルデータと処理情報を含む辞書
                {
                    'ecg_samples': list,  # ECGサンプル値のリスト
                    'timestamps': list,   # 各サンプルのタイムスタンプ（絶対時刻ナノ秒数）
                }
        """
        # 最小ヘッダーサイズ確認
        if len(raw_data) < 10:
            raise ValueError(f"Insufficient ECG data length: {len(raw_data)} bytes")

        # データタイプがECGかチェック
        if raw_data[0] != 0x00:
            raise ValueError(f"Received unknown data type: {raw_data[0]}")
        
        try:
            # タイムスタンプを抽出
            timestamp = self.convert_to_unsigned_long(raw_data, 1, 8)
            
            # フレームタイプを抽出
            frame_type = raw_data[9]
            
            # ECGサンプルデータを抽出
            ecg_payload_bytes = raw_data[10:]

            ecg_samples = []
            timestamps = []

            # 3バイト/サンプル処理（24bit signed integer）
            if frame_type == 0x00:
                bytes_per_ecg_sample = 3
                ecg_samples_count = len(ecg_payload_bytes) // bytes_per_ecg_sample
                
                for i in range(ecg_samples_count):
                    byte_offset = i * bytes_per_ecg_sample
                    current_sample_bytes = ecg_payload_bytes[byte_offset:byte_offset + bytes_per_ecg_sample]
                    
                    # 24ビット符号付き整数に変換
                    ecg_value = self.convert_array_to_signed_int(current_sample_bytes, 0, bytes_per_ecg_sample)
                    
                    # サンプル時刻計算（130Hzでの各サンプル時刻）
                    current_sample_timestamp_ns = timestamp + (i * 1_000_000_000 // 130)
                    
                    ecg_samples.append(ecg_value)
                    timestamps.append(current_sample_timestamp_ns)
                
                return {
                    'ecg_samples': ecg_samples,
                    'timestamps': timestamps,
                }
            else:
                raise ValueError(f"Unsupported frame type: {frame_type}")
                
        except Exception as e:
            raise ValueError(f"Failed to parse ECG data: {e}")


class ECGInterface:
    """
    Polar ECG専用インターフェースクラス
    
    機能:
    - Polar H10センサーとのBLE接続管理
    - ECGデータストリーミングの開始・停止
    - 生ECGデータの受信と解析結果の配信
    - 過渡応答期間のデータフィルタリング
    """
    
    def __init__(self) -> None:
        """
        Polar ECGインターフェースを初期化
        """
        self.device_id: str = ECG_POLAR_DEVICE_ID
        self.device: Optional[BLEDevice] = None  # BLEDeviceオブジェクトを保持
        self.device_address: Optional[str] = None
        self.device_name: Optional[str] = None
        self.client: Optional[BleakClient] = None
        self.is_connected: bool = False
        self.is_streaming: bool = False
        self.ecg_callback: Optional[ECGCallback] = None

        # 過渡応答除外関連
        self.streaming_start_time_ns: Optional[int] = None
        self.transition_period_seconds: float = TRANSITION_PERIOD_SECONDS
        self.transition_period_passed: bool = False  # 過渡応答期間が終了したかのフラグ

        self.data_formatter: ECGDataFormatter = ECGDataFormatter()
        
        # DEBUG: 切断検出用
        self._disconnection_detected: bool = False

    def set_ecg_callback(self, callback: ECGCallback) -> None:
        """
        ECGデータ受信時のコールバック関数を設定
        
        Args:
            callback: ECGデータを受信した際に呼び出される関数
        """
        self.ecg_callback = callback
    
    async def find_polar_device(self) -> Optional[BLEDevice]:
        """
        Polarデバイスを検出
        
        Returns:
            BLEDevice: 見つかったデバイスオブジェクト、見つからない場合はNone
        """
        logger.info(f"Searching for Polar device with ID: {self.device_id}")
        devices = await BleakScanner.discover(timeout=ECG_TIMEOUT_SECONDS)
        
        for device in devices:
            if device.name and "Polar" in device.name and self.device_id in device.name:
                logger.info(f"Found target Polar device: {device.name} ({device.address})")
                self.device_name = device.name
                self.device_address = device.address
                return device
        
        return None
    
    def _filter_transition_data(self, ecg_result: ECGDataResult) -> Optional[ECGDataResult]:
        """
        過渡応答期間のデータをフィルタリング
        
        Args:
            ecg_result: ECGデータ結果
            
        Returns:
            フィルタリング後のECGデータ、過渡応答期間中の場合はNone
        """
        # 過渡応答期間が既に終了している場合はフィルタリングしない
        if self.transition_period_passed:
            return ecg_result
        
        # 最初のデータ受信時にストリーミング開始時刻を設定
        if self.streaming_start_time_ns is None:
            timestamps = ecg_result.get('timestamps', [])
            if timestamps:
                self.streaming_start_time_ns = timestamps[0]
                logger.info("Set streaming start time for transition filtering")
        
        if self.streaming_start_time_ns is None:
            # タイムスタンプが取得できない場合はデータを破棄
            return None
        
        # パケット内のタイムスタンプをチェック
        timestamps = ecg_result.get('timestamps', [])
        ecg_samples = ecg_result.get('ecg_samples', [])
        
        if not timestamps or not ecg_samples:
            return None
        
        # 過渡応答期間を超えたサンプルのインデックスを見つける
        valid_indices = []
        for i, timestamp_ns in enumerate(timestamps):
            elapsed_seconds = (timestamp_ns - self.streaming_start_time_ns) / 1_000_000_000
            if elapsed_seconds >= self.transition_period_seconds:
                valid_indices.append(i)
        
        # 有効なサンプルがない場合
        if not valid_indices:
            return None
        
        # 有効なサンプルがある場合
        if valid_indices:
            # 部分的にフィルタリング
            filtered_samples = [ecg_samples[i] for i in valid_indices]
            filtered_timestamps = [timestamps[i] for i in valid_indices]
            
            self.transition_period_passed = True  # 過渡応答期間終了
            logger.info("Transition period completed - no more filtering needed")
            
            return {
                'ecg_samples': filtered_samples,
                'timestamps': filtered_timestamps
            }
    
    async def ecg_notification_handler(self, sender: int, data: bytearray) -> None:
        """ECGデータの通知を処理（polar_h10_get_ecg.py仕様準拠）"""
        try:
            # ECGデータ解析（PMD仕様準拠）
            ecg_result = self.data_formatter.parse_ecg_data(data)
            
            # 過渡応答期間のデータをフィルタリング
            filtered_result = self._filter_transition_data(ecg_result)
            if filtered_result is None:
                return
            
            # データをリストに蓄積
            ecg_samples = filtered_result['ecg_samples']
            timestamps = filtered_result['timestamps']
            
            ecg_samples_count = len(ecg_samples)
            logger.info(f"Processed {ecg_samples_count} ECG samples from packet (frame_type=0)")
            
            # コールバック実行
            if self.ecg_callback:
                self.ecg_callback(filtered_result)
            else:
                logger.warning("ECG callback is None - data will not be processed!")
                
        except Exception as e:
            logger.error(f"Error processing ECG data: {e}")
    
    def _disconnection_callback(self, client: BleakClient) -> None:
        """BLE切断時のコールバック"""
        logger.warning(f"BLE disconnection detected! Device: {self.device_address}")
        self._disconnection_detected = True
        self.is_connected = False
        self.is_streaming = False
    
    async def connect(self) -> bool:
        """
        Polarセンサーに接続
        
        Returns:
            bool: 接続成功時True、失敗時False
        """
        try:
            # デバイスを検出
            self.device = await self.find_polar_device()
            
            if self.device is None:
                logger.error(f"Polar device with ID '{self.device_id}' not found")
                return False
            
            logger.info(f"Connecting to ECG device: {self.device_address}")
            
            # CRITICAL FIX: BLEDeviceオブジェクトを直接使用して接続
            self._disconnection_detected = False
            self.client = BleakClient(
                self.device,  # アドレス文字列ではなくBLEDeviceオブジェクトを使用
                disconnected_callback=self._disconnection_callback
            )
            
            await self.client.connect()
            self.is_connected = True
            logger.info("Successfully connected to ECG service")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to ECG service: {e}")
            return False
    
    async def disconnect(self) -> None:
        """接続を切断"""
        if self.is_streaming:
            await self.stop_ecg_streaming()
            
        if self.client and self.is_connected:
            try:
                await self.client.disconnect()
                self.is_connected = False
                logger.info("Successfully disconnected from ECG service")
            except Exception as e:
                logger.error(f"Failed to disconnect from ECG service: {e}")
    
    async def start_ecg_streaming(self) -> bool:
        """ECGストリーミングを開始"""
        if not self.is_connected or not self.client:
            logger.error("Not connected to ECG device")
            return False
            
        try:
            # ストリーミング状態を先に設定
            self.is_streaming = True
            
            # ストリーミング開始時刻の初期化
            self.streaming_start_time_ns = None
            self.transition_period_passed = False
            
            # ECG測定の通知を開始
            await self.client.start_notify(ECG_DATA_UUID, self.ecg_notification_handler)
            
            # Polar H10がnotification登録を完全に処理するまで待機
            await asyncio.sleep(2.0)
            
            # ECGストリーミング開始コマンドを送信
            start_command = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
            await self.client.write_gatt_char(ECG_CONTROL_POINT_UUID, start_command)
            
            # デバイスがコマンドを処理するまで待機
            await asyncio.sleep(2.0)
            
            if not self.client.is_connected:
                logger.error("BLE session closed unexpectedly after streaming command!")
                self.is_streaming = False
                return False
            
            logger.info("ECG streaming started - waiting for data...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start ECG streaming: {e}")
            self.is_streaming = False
            return False
    
    async def stop_ecg_streaming(self) -> None:
        """ECGストリーミングを停止"""
        if not self.is_streaming:
            logger.debug("ECG streaming is not active")
            return
            
        try:
            # クライアントが接続されているかチェック
            if self.client and self.client.is_connected:
                # ECGストリーミング停止コマンドを送信（PMDプロトコル準拠）
                stop_command = bytearray([0x03, 0x00])  # ECGストリーミング停止
                await self.client.write_gatt_char(ECG_CONTROL_POINT_UUID, stop_command)
                
                # 通知を停止
                await self.client.stop_notify(ECG_DATA_UUID)
                
                logger.info("ECG streaming stopped")
            else:
                logger.warning("Client not connected - cannot send stop command")
                
        except Exception as e:
            logger.error(f"Failed to stop ECG streaming: {e}")
        finally:
            self.is_streaming = False

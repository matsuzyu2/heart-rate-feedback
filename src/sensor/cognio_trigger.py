# Cognio EEGシステム用トリガー送信モジュール
import zmq
import serial
import logging
from typing import Optional, TYPE_CHECKING

# 設定を読み込み
from ..config.ecg_config import (
    COGNIO_ZMQ_ADDRESS,
    COGNIO_SERIAL_PORT,
    COGNIO_SERIAL_BAUDRATE,
    ENABLE_COGNIO_TRIGGER
)

# 型チェック時のみインポート（循環インポート回避）
if TYPE_CHECKING:
    from ..logger.cognio_trigger_logger import CognioTriggerLogger

# ログ設定
logger = logging.getLogger(__name__)


class CognioTrigger:
    """
    Cognio EEGシステムへのトリガー送信クラス
    
    機能:
    - ZMQ通信（PUSHパターン）でのトリガー送信
    - シリアル通信でのトリガー送信
    - 両方の通信チャネルに対する非同期トリガー送信
    - トリガー送信イベントのログ記録
    """
    
    def __init__(self) -> None:
        """
        CognioTriggerを初期化
        """
        self.zmq_context: Optional[zmq.Context] = None
        self.zmq_socket: Optional[zmq.Socket] = None
        self.serial_connection: Optional[serial.Serial] = None
        self.zmq_connected: bool = False
        self.serial_connected: bool = False
        
        self.zmq_address: str = COGNIO_ZMQ_ADDRESS
        self.serial_port: str = COGNIO_SERIAL_PORT
        self.serial_baudrate: int = COGNIO_SERIAL_BAUDRATE
        self.enabled: bool = ENABLE_COGNIO_TRIGGER
        
        # ロガーはセッションコントローラーから設定される
        self.trigger_logger: Optional['CognioTriggerLogger'] = None
        
        logger.info(f"CognioTrigger initialized (enabled={self.enabled})")
    
    async def connect(self) -> bool:
        """
        ZMQとシリアル接続を確立（少なくとも1つが成功すればTrue）
        
        Returns:
            bool: 少なくとも1つの接続が成功した場合True、すべて失敗した場合False
        """
        if not self.enabled:
            logger.info("Cognio trigger is disabled in config")
            return True  # 無効時は成功として扱う
        
        if self.zmq_connected or self.serial_connected:
            logger.warning("Cognio trigger already connected")
            return True
        
        # ZMQ接続の確立を試行
        try:
            logger.info(f"Connecting to Cognio via ZMQ: {self.zmq_address}")
            self.zmq_context = zmq.Context()
            self.zmq_socket = self.zmq_context.socket(zmq.PUSH)
            # 送信タイムアウトを設定（ミリ秒）
            self.zmq_socket.setsockopt(zmq.SNDTIMEO, 1000)
            self.zmq_socket.connect(self.zmq_address)
            self.zmq_connected = True
            logger.info("ZMQ connection established")
        except zmq.ZMQError as e:
            logger.warning(f"Failed to establish ZMQ connection: {e}")
            self.zmq_connected = False
        except Exception as e:
            logger.warning(f"Unexpected error during ZMQ connection: {e}")
            self.zmq_connected = False
        
        # シリアル接続の確立を試行
        try:
            logger.info(f"Connecting to Cognio via Serial: {self.serial_port} @ {self.serial_baudrate}bps")
            self.serial_connection = serial.Serial(
                port=self.serial_port,
                baudrate=self.serial_baudrate,
                timeout=1
            )
            self.serial_connected = True
            logger.info("Serial connection established")
        except serial.SerialException as e:
            logger.warning(f"Failed to establish serial connection: {e}")
            self.serial_connected = False
        except Exception as e:
            logger.warning(f"Unexpected error during serial connection: {e}")
            self.serial_connected = False
        
        # 少なくとも1つの接続が成功したか確認
        if self.zmq_connected or self.serial_connected:
            logger.info(f"Successfully connected to Cognio trigger system (ZMQ: {self.zmq_connected}, Serial: {self.serial_connected})")
            return True
        else:
            logger.error("Failed to establish any connection to Cognio trigger system")
            await self.disconnect()
            return False
    
    async def disconnect(self) -> None:
        """
        ZMQとシリアル接続をクローズ
        """
        if not self.enabled:
            return
        
        if not self.zmq_connected and not self.serial_connected:
            logger.debug("Cognio trigger already disconnected")
            return
        
        try:
            # シリアル接続のクローズ
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                logger.info("Serial connection closed")
            self.serial_connection = None
            self.serial_connected = False
            
            # ZMQ接続のクローズ
            if self.zmq_socket:
                # Lingerを0に設定してすぐにクローズ
                self.zmq_socket.setsockopt(zmq.LINGER, 0)
                self.zmq_socket.close()
                logger.info("ZMQ socket closed")
            self.zmq_socket = None
            
            if self.zmq_context:
                # コンテキストを即座に終了（未送信メッセージを破棄）
                self.zmq_context.destroy(linger=0)
                logger.info("ZMQ context terminated")
            self.zmq_context = None
            self.zmq_connected = False
            
            logger.info("Successfully disconnected from Cognio trigger system")
            
        except Exception as e:
            logger.error(f"Error during Cognio trigger disconnection: {e}")
    
    async def send_trigger(self, trigger_code: int, annotation: str = "") -> bool:
        """
        ZMQとシリアル両方にトリガーパルスを送信し、ログに記録
        トリガーは trigger_code → 0 のセットで送信される
        
        Args:
            trigger_code (int): トリガーコード
                - 100: バイオフィードバックイベント
            annotation (str): イベントの説明（例: "Session_Start", "Feedback_High"）
        
        Returns:
            bool: 少なくとも1つの送信が成功した場合True、すべて失敗した場合False
        """
        if not self.enabled:
            logger.debug(f"Cognio trigger disabled - skipping trigger {trigger_code}")
            return True  # 無効時は成功として扱う
        
        if not self.zmq_connected and not self.serial_connected:
            logger.error("Cannot send trigger - not connected to Cognio")
            return False
        
        import asyncio
        
        zmq_success = False
        serial_success = False
        
        # ZMQ経由でトリガーパルス送信（接続されている場合のみ）
        if self.zmq_connected and self.zmq_socket:
            try:
                logger.info(f"Sending trigger pulse {trigger_code} via ZMQ")
                # トリガーコードを送信
                self.zmq_socket.send_string(str(trigger_code), flags=zmq.NOBLOCK)
                await asyncio.sleep(0.1)  # 100ms待機
                # リセット信号を送信
                self.zmq_socket.send_string("0", flags=zmq.NOBLOCK)
                logger.info(f"ZMQ trigger pulse {trigger_code}→0 sent successfully")
                zmq_success = True
            except zmq.Again:
                logger.warning(f"ZMQ send would block - trigger {trigger_code} may not be delivered")
                zmq_success = False
            except zmq.ZMQError as e:
                logger.error(f"Failed to send trigger via ZMQ: {e}")
                zmq_success = False
            except Exception as e:
                logger.error(f"Unexpected error sending trigger via ZMQ: {e}")
                zmq_success = False
        
        # シリアル経由でトリガーパルス送信（接続されている場合のみ）
        if self.serial_connected and self.serial_connection and self.serial_connection.is_open:
            try:
                logger.info(f"Sending trigger pulse {trigger_code} via Serial")
                # トリガーコードを送信
                self.serial_connection.write(bytes([trigger_code]))
                await asyncio.sleep(0.1)  # 100ms待機
                # リセット信号を送信
                self.serial_connection.write(bytes([0]))
                logger.info(f"Serial trigger pulse {trigger_code}→0 sent successfully")
                serial_success = True
            except serial.SerialException as e:
                logger.error(f"Failed to send trigger via Serial: {e}")
                serial_success = False
            except Exception as e:
                logger.error(f"Unexpected error sending trigger via Serial: {e}")
                serial_success = False
        
        # 少なくとも1つが成功したか確認
        if zmq_success or serial_success:
            logger.info(f"Trigger pulse {trigger_code} sent successfully (ZMQ: {zmq_success}, Serial: {serial_success})")
            
            # トリガー送信をCSVログに記録
            if self.trigger_logger and annotation:
                try:
                    self.trigger_logger.log_trigger(trigger_code, annotation)
                    logger.debug(f"Trigger event logged: {trigger_code} - {annotation}")
                except Exception as e:
                    logger.warning(f"Failed to log trigger event: {e}")
            
            return True
        else:
            logger.error(f"Failed to send trigger pulse {trigger_code} via all available channels")
            return False

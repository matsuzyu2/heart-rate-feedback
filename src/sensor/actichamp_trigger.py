# actiCHamp EEGシステム用トリガー送信モジュール
import serial
import logging
from typing import Optional, TYPE_CHECKING
import time

# 設定を読み込み
from ..config.ecg_config import (
    ACTICHAMP_SERIAL_PORT,
    ACTICHAMP_SERIAL_BAUDRATE,
    ENABLE_ACTICHAMP_TRIGGER
)

# 型チェック時のみインポート（循環インポート回避）
if TYPE_CHECKING:
    from ..logger.actichamp_trigger_logger import ActiChampTriggerLogger

# ログ設定
logger = logging.getLogger(__name__)


class ActiChampTrigger:
    """
    actiCHamp EEGシステムへのトリガー送信クラス
    """
    
    def __init__(self) -> None:
        """
        ActiChampTriggerを初期化
        """
        self.serial_connection: Optional[serial.Serial] = None
        self.serial_connected: bool = False
        
        self.serial_port: str = ACTICHAMP_SERIAL_PORT
        self.serial_baudrate: int = ACTICHAMP_SERIAL_BAUDRATE
        self.enabled: bool = ENABLE_ACTICHAMP_TRIGGER
        
        # ロガーはセッションコントローラーから設定される
        self.trigger_logger: Optional['ActiChampTriggerLogger'] = None
        
        logger.info(f"ActiChampTrigger initialized (enabled={self.enabled})")
    
    async def connect(self) -> bool:
        """
        シリアル接続を確立
        
        Returns:
            bool: 接続成功時True、失敗時False
        """
        if not self.enabled:
            logger.info("actiCHamp trigger is disabled in config")
            return True  # 無効時は成功として扱う
        
        if self.serial_connected:
            return True
        
        # シリアル接続の確立を試行
        try:
            self.serial_connection = serial.Serial(
                port=self.serial_port,
                baudrate=self.serial_baudrate,
            )
            self.serial_connected = True
            logger.info("Serial connection established")
        except serial.SerialException as e:
            logger.warning(f"Failed to establish serial connection: {e}")
            self.serial_connected = False
        except Exception as e:
            logger.warning(f"Unexpected error during serial connection: {e}")
            self.serial_connected = False
        if self.serial_connected:
            logger.info("Successfully connected to actiCHamp trigger system")
            return True
    
    async def disconnect(self) -> None:
        """
        シリアル接続をクローズ
        """
        if not self.enabled:
            return
        
        if not self.serial_connected:
            return
        
        try:
            # シリアル接続のクローズ
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                logger.info("Serial connection closed")
            self.serial_connection = None
            self.serial_connected = False
            
            logger.info("Successfully disconnected from actiCHamp trigger system")
            
        except Exception as e:
            logger.error(f"Error during actiCHamp trigger disconnection: {e}")
    
    async def send_trigger(self, trigger_code: int, annotation: str = "") -> bool:
        """
        トリガーは trigger_code → 0 のセットで送信される
        
        Args:
            trigger_code (int): トリガーコード
            annotation (str): イベントの説明（例: "Session_Start", "Feedback_High"）
        
        Returns:
            bool: 送信成功時True、失敗時False
        """
        if not self.enabled:
            logger.debug(f"actiCHamp trigger disabled - skipping trigger {trigger_code}")
            return True  # 無効時は成功として扱う
        
        if not self.serial_connected:
            logger.error("Cannot send trigger - not connected to actiCHamp")
            return False
        
        serial_success = False
        
        # シリアル経由でトリガーパルス送信（接続されている場合のみ）
        if self.serial_connected and self.serial_connection and self.serial_connection.is_open:
            try:
                # トリガーコードを送信
                self.serial_connection.write(bytes([trigger_code]))
                time.sleep(0.05)  # 50ms待機
                self.serial_connection.write(bytes([0]))
                logger.info(f"Serial trigger pulse {trigger_code}→0 sent successfully")
                serial_success = True
            except serial.SerialException as e:
                logger.error(f"Failed to send trigger via Serial: {e}")
                serial_success = False
            except Exception as e:
                logger.error(f"Unexpected error sending trigger via Serial: {e}")
                serial_success = False
        
        if serial_success:      
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

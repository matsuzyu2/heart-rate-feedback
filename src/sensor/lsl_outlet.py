"""
LSL (Lab Streaming Layer) アウトレットモジュール
心拍バイオフィードバックシステムのイベントマーカーをLSL経由で配信

"""
from typing import Optional
import logging

try:
    from pylsl import StreamInfo, StreamOutlet
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False

logger = logging.getLogger(__name__)


class LSLOutlet:
    """
    LSLマーカーストリームを管理するクラス
    """
    
    def __init__(
        self,
        stream_name: str = "HeartRate_Biofeedback_LSL",
        stream_type: str = "Markers",
        source_id: str = "hr_biofeedback_marker"
    ):
        """
        LSLアウトレットの初期化
        
        Args:
            stream_name: ストリーム名（デフォルト: "HeartRate_Biofeedback_LSL"）
            stream_type: ストリームタイプ（デフォルト: "Markers"）
            source_id: ソースID - 一意の識別子（デフォルト: "hr_biofeedback_marker"）
        """
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.source_id = source_id
        self.outlet: Optional[StreamOutlet] = None
        self.is_active = False
        
        if not LSL_AVAILABLE:
            logger.warning("pylsl is not installed. LSL outlet will not be available.")
    
    def initialize(self) -> bool:
        """
        LSLストリームを初期化してブロードキャスト開始
        
        Returns:
            bool: 初期化成功時True
        """
        if not LSL_AVAILABLE:
            logger.error("Cannot initialize LSL: pylsl not installed")
            return False
        
        try:
            info = StreamInfo(
                name=self.stream_name,
                type=self.stream_type,
                channel_count=1,
                nominal_srate=0,  # イベントマーカーなので不規則サンプリング
                channel_format='int32',
                source_id=self.source_id
            )
            
            # アウトレットを作成してブロードキャスト開始
            self.outlet = StreamOutlet(info)
            self.is_active = True
            
            logger.info(f"LSL outlet initialized: {self.stream_name}")
            logger.info(f"  - Type: {self.stream_type}")
            logger.info(f"  - Source ID: {self.source_id}")
            logger.info(f"  - Channel count: 1, Format: int32")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize LSL outlet: {e}")
            return False
    
    def send_trigger(self, value: int) -> bool:
        """
        LSL経由でトリガーマーカーを送信
        
        Args:
            value: 送信するマーカー値（整数）
        
        Returns:
            bool: 送信成功時True
        """
        if not self.is_active or self.outlet is None:
            logger.warning(f"LSL outlet not active. Cannot send trigger: {value}")
            return False
        
        try:     
            # valueが整数であることを確認
            if not isinstance(value, int):
                logger.error(f"Invalid trigger value type: expected int, got {type(value).__name__}")
                # リストの場合は最初の要素を取り出す
                if isinstance(value, (list, tuple)) and len(value) > 0:
                    value = int(value[0])
                    logger.warning(f"Converted list/tuple to int: {value}")
                else:
                    return False
            
            self.outlet.push_sample([value])
            logger.info(f"LSL trigger sent: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send LSL trigger [{value}]: {e}")
            return False
    
    def close(self) -> None:
        """
        LSLアウトレットをクローズ
        """
        if self.outlet:
            self.outlet = None
            self.is_active = False
            logger.info("LSL outlet closed")

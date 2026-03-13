"""
フィードバックモード実装
"""
from abc import ABC, abstractmethod
import random
from typing import Protocol


class AudioFeedbackProtocol(Protocol):
    """
    音声フィードバックのプロトコル(インターフェース分離原則)
    """
    def play_high(self) -> None:
        """心拍数上昇音を再生"""
        ...
    
    def play_low(self) -> None:
        """心拍数下降音を再生"""
        ...


class FeedbackMode(ABC):
    """
    フィードバックモードの抽象基底クラス
    """
    
    def __init__(self, audio_feedback: AudioFeedbackProtocol):
        """
        フィードバックモードの初期化
        
        Args:
            audio_feedback: 音声フィードバックインターフェース
        """
        self.audio_feedback = audio_feedback
        self.lsl_outlet = None  # LSLアウトレット（オプション）
    
    def initialize_audio(self) -> None:
        """
        音声フィードバックを初期化
        
        ECG接続後に呼び出す必要があります。
        AudioFeedbackがinitialize()メソッドを持つ場合
        """
        if hasattr(self.audio_feedback, 'initialize'):
            self.audio_feedback.initialize()
    
    def _send_lsl_trigger(self, trigger_value: int) -> None:
        """
        LSLトリガーを送信（内部ヘルパーメソッド）
        
        Args:
            trigger_value: 送信するトリガー値
        """
        if self.lsl_outlet and hasattr(self.lsl_outlet, 'is_active') and self.lsl_outlet.is_active:
            try:
                if self.lsl_outlet.send_trigger(trigger_value):
                    import logging
                    logging.getLogger(__name__).info(f"LSL trigger sent: {trigger_value}")
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send LSL trigger {trigger_value}: {e}")
    
    @abstractmethod
    def process_feedback(self, trend: str, average_hr_bpm: float = None) -> str:
        """
        トレンドに基づいてフィードバックを処理
        
        Args:
            trend: "increasing", "decreasing", "stable"
            average_hr_bpm: 5秒間の平均心拍数（BPM）、オプショナル
            
        Returns:
            str: 再生した音の種類 ("high", "low", "none")
        """
        pass


class IncreaseRewardMode(FeedbackMode):
    """
    増加報酬モード
    """
    
    def process_feedback(self, trend: str, average_hr_bpm: float = None) -> str:
        """
        心拍数のトレンドに基づいてフィードバックを処理
        
        Args:
            trend: 心拍数のトレンド
            average_hr_bpm: 5秒間の平均心拍数（BPM）、オプショナル
            
        Returns:
            str: 再生した音の種類 ("high", "low", "none")
        """
        if trend == "increasing":
            self.audio_feedback.play_high()
            # LSLトリガー送信(Cognioトリガーの後)
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_HIGH
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_HIGH)
            return "high"
        elif trend == "decreasing":
            self.audio_feedback.play_low()
            # LSLトリガー送信(Cognioトリガーの後)
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_LOW
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_LOW)
            return "low"
        # "stable"の場合は何もしない(YAGNI: 現在は安定時の処理不要)
        return "none"


class DecreaseRewardMode(FeedbackMode):
    """
    減少報酬モード
    """
    
    def process_feedback(self, trend: str, average_hr_bpm: float = None) -> str:
        """
        心拍数のトレンドに基づいてフィードバックを処理
        
        Args:
            trend: 心拍数のトレンド
            average_hr_bpm: 5秒間の平均心拍数（BPM）、オプショナル
            
        Returns:
            str: 再生した音の種類 ("high", "low", "none")
        """
        if trend == "decreasing":
            self.audio_feedback.play_low()
            # LSLトリガー送信(Cognioトリガーの後)
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_LOW
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_LOW)
            return "low"
        elif trend == "increasing":
            self.audio_feedback.play_high()
            # LSLトリガー送信(Cognioトリガーの後)
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_HIGH
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_HIGH)
            return "high"
        # "stable"の場合は何もしない
        return "none"


class RandomMode(FeedbackMode):
    """
    ランダムモード（対照群）
    """
    
    def __init__(self, audio_feedback: AudioFeedbackProtocol):
        """
        ランダムモードの初期化
        
        Args:
            audio_feedback: 音声フィードバックインターフェース
        """
        super().__init__(audio_feedback)
        from ..config.ecg_config import RANDOM_MODE_WEIGHTS, RANDOM_MODE_TOTAL_FEEDBACKS
        
        sequence = []
        for feedback_type, weight in RANDOM_MODE_WEIGHTS.items():
            count = int(RANDOM_MODE_TOTAL_FEEDBACKS * weight)
            sequence.extend([feedback_type] * count)
        
        # 端数を補正
        sequence.extend(['stable'] * (RANDOM_MODE_TOTAL_FEEDBACKS - len(sequence)))
        
        random.shuffle(sequence)
        
        self._feedback_queue = sequence
        self._index = 0
    
    def process_feedback(self, trend: str, average_hr_bpm: float = None) -> str:
        """
        事前に決定されたシーケンスから次のフィードバックを取り出して処理
        
        Args:
            trend: 心拍数のトレンド（このモードでは使用しない）
            average_hr_bpm: 5秒間の平均心拍数（BPM）、オプショナル
            
        Returns:
            str: 再生した音の種類 ("high", "low", "none")
        """
        if self._index >= len(self._feedback_queue):
            return "none"
        
        feedback_type = self._feedback_queue[self._index]
        self._index += 1
        
        if feedback_type == 'high':
            self.audio_feedback.play_high()
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_HIGH
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_HIGH)
            return "high"
        elif feedback_type == 'low':
            self.audio_feedback.play_low()
            from ..config.ecg_config import LSL_TRIGGER_FEEDBACK_LOW
            self._send_lsl_trigger(LSL_TRIGGER_FEEDBACK_LOW)
            return "low"
        else:  # stable
            return "none"

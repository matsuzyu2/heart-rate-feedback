"""
音声フィードバック制御
"""
import pygame
import logging
from typing import Optional
from pathlib import Path

# ログ設定
logger = logging.getLogger(__name__)


class AudioFeedbackError(Exception):
    """音声フィードバック関連のエラー"""
    pass


class AudioFeedback:
    """
    音声フィードバッククラス
    心拍数変化に応じた音声再生、Cognioトリガー送信
    """
    
    def __init__(self, high_sound: str, low_sound: str, cognio_trigger=None, actichamp_trigger=None):
        """
        音声フィードバックの初期化(遅延初期化パターン)
        
        Args:
            high_sound: 心拍数上昇時の音声ファイルパス
            low_sound: 心拍数下降時の音声ファイルパス
            cognio_trigger: CognioTriggerインスタンス(オプション)
            actichamp_trigger: ActiChampTriggerインスタンス(オプション)
            
        Raises:
            AudioFeedbackError: 音声ファイルが存在しない場合
            
        Note:
            pygame.mixerは初期化されません。
            initialize()を明示的に呼び出す必要があります。
        """
        self.high_sound_path = high_sound
        self.low_sound_path = low_sound
        self.cognio_trigger = cognio_trigger
        self.actichamp_trigger = actichamp_trigger
        self._initialized = False
        
        # ファイル存在チェック  
        self._validate_sound_files()
    
    def initialize(self) -> None:
        """
        pygame.mixerを初期化
        
        ECG,EEGデバイスの接続が完了した後に呼び出す必要があります。
        
        Raises:
            AudioFeedbackError: pygame mixerの初期化に失敗した場合
        """
        if self._initialized:
            return
        
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
                self._initialized = True
            else:
                self._initialized = True
                
        except pygame.error as e:
            raise AudioFeedbackError(f"Failed to initialize pygame mixer: {e}")
    
    def _validate_sound_files(self) -> None:
        """
        音声ファイルの存在を検証
        
        Raises:
            AudioFeedbackError: ファイルが存在しない場合
        """
        for sound_path in [self.high_sound_path, self.low_sound_path]:
            if not Path(sound_path).exists():
                raise AudioFeedbackError(f"Sound file not found: {sound_path}")
    
    def play_high(self) -> None:
        """
        心拍数上昇時の音を再生し、Cognioトリガー・LSLトリガーを送信
        
        YAGNI: 現在はシンプルな再生のみ
        将来的に音量制御や重複再生制御が必要になったら追加
        
        Raises:
            AudioFeedbackError: 音声再生に失敗した場合
        """
        if not self._initialized:
            raise AudioFeedbackError("AudioFeedback not initialized. Call initialize() first.")
        
        try:
            # 心拍数上昇音を再生
            sound = pygame.mixer.Sound(self.high_sound_path)
            sound.play()
            logger.debug("High sound played successfully")
            
            # Cognioトリガーを送信(非同期)
            if self.cognio_trigger:
                import asyncio
                try:
                    # イベントループを取得して非同期タスクを実行
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既存のイベントループで実行
                        asyncio.create_task(self._send_high_trigger())
                    else:
                        # イベントループが実行されていない場合は同期実行
                        loop.run_until_complete(self._send_high_trigger())
                except RuntimeError:
                    # イベントループがない場合は新しいループを作成
                    asyncio.run(self._send_high_trigger())
            
            # actiCHampトリガーを送信(非同期)
            if self.actichamp_trigger:
                import asyncio
                try:
                    # イベントループを取得して非同期タスクを実行
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既存のイベントループで実行
                        asyncio.create_task(self._send_actichamp_high_trigger())
                    else:
                        # イベントループが実行されていない場合は同期実行
                        loop.run_until_complete(self._send_actichamp_high_trigger())
                except RuntimeError:
                    # イベントループがない場合は新しいループを作成
                    asyncio.run(self._send_actichamp_high_trigger())
        except pygame.error as e:
            raise AudioFeedbackError(f"Failed to play high sound: {e}")
    
    async def _send_high_trigger(self) -> None:
        """心拍数上昇トリガーをCognioに送信"""
        from ..config.ecg_config import COGNIO_TRIGGER
        try:
            await self.cognio_trigger.send_trigger(COGNIO_TRIGGER, "Feedback_High")
        except Exception as e:
            logger.warning(f"Failed to send high trigger to Cognio: {e}")
    
    async def _send_actichamp_high_trigger(self) -> None:
        """心拍数上昇トリガーをactiCHampに送信"""
        from ..config.ecg_config import ACTICHAMP_TRIGGER
        try:
            await self.actichamp_trigger.send_trigger(ACTICHAMP_TRIGGER, "Feedback_High")
        except Exception as e:
            logger.warning(f"Failed to send high trigger to actiCHamp: {e}")
    
    def play_low(self) -> None:
        """
        心拍数下降時の音を再生し、Cognioトリガー・LSLトリガーを送信
        
        Raises:
            AudioFeedbackError: 音声再生に失敗した場合
        """
        if not self._initialized:
            raise AudioFeedbackError("AudioFeedback not initialized. Call initialize() first.")
        
        try:
            # 心拍数下降音を再生
            sound = pygame.mixer.Sound(self.low_sound_path)
            sound.play()
            logger.debug("Low sound played successfully")
            
            # Cognioトリガーを送信(非同期)
            if self.cognio_trigger:
                import asyncio
                try:
                    # イベントループを取得して非同期タスクを実行
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既存のイベントループで実行
                        asyncio.create_task(self._send_low_trigger())
                    else:
                        # イベントループが実行されていない場合は同期実行
                        loop.run_until_complete(self._send_low_trigger())
                except RuntimeError:
                    # イベントループがない場合は新しいループを作成
                    asyncio.run(self._send_low_trigger())
            
            # actiCHampトリガーを送信(非同期)
            if self.actichamp_trigger:
                import asyncio
                try:
                    # イベントループを取得して非同期タスクを実行
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既存のイベントループで実行
                        asyncio.create_task(self._send_actichamp_low_trigger())
                    else:
                        # イベントループが実行されていない場合は同期実行
                        loop.run_until_complete(self._send_actichamp_low_trigger())
                except RuntimeError:
                    # イベントループがない場合は新しいループを作成
                    asyncio.run(self._send_actichamp_low_trigger())
        except pygame.error as e:
            raise AudioFeedbackError(f"Failed to play low sound: {e}")
    
    async def _send_low_trigger(self) -> None:
        """心拍数下降トリガーをCognioに送信"""
        from ..config.ecg_config import COGNIO_TRIGGER
        try:
            await self.cognio_trigger.send_trigger(COGNIO_TRIGGER, "Feedback_Low")
        except Exception as e:
            logger.warning(f"Failed to send low trigger to Cognio: {e}")
    
    async def _send_actichamp_low_trigger(self) -> None:
        """心拍数下降トリガーをactiCHampに送信"""
        from ..config.ecg_config import ACTICHAMP_TRIGGER
        try:
            await self.actichamp_trigger.send_trigger(ACTICHAMP_TRIGGER, "Feedback_Low")
        except Exception as e:
            logger.warning(f"Failed to send low trigger to actiCHamp: {e}")

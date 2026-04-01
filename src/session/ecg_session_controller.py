"""
ECGセッション制御モジュール
ECGベースの実験セッションの開始・停止とコンポーネント統合を担当
"""
import asyncio
import logging
from typing import Optional

from ..sensor.ecg_interface import ECGInterface
from ..sensor.cognio_trigger import CognioTrigger
from ..sensor.actichamp_trigger import ActiChampTrigger
from ..sensor.lsl_outlet import LSLOutlet
from ..processing.ecg_processor import ECGProcessor
from ..processing.simple_r_peak_detector import BeatEvent
from ..logger.ecg_logger import ECGLogger
from ..logger.beat_event_logger import BeatEventLogger
from ..logger.instantaneous_hr_logger import InstantaneousHRLogger
from ..logger.feedback_event_logger import FeedbackEventLogger
from ..logger.cognio_trigger_logger import CognioTriggerLogger
from ..logger.actichamp_trigger_logger import ActiChampTriggerLogger
from ..feedback.feedback_modes import FeedbackMode

from ..config.ecg_config import (
    SESSION_DURATION_SECONDS,
    COGNIO_TRIGGER,
    ACTICHAMP_TRIGGER,
    ENABLE_LSL,
    LSL_STREAM_NAME,
    LSL_TRIGGER_SESSION_START,
    LSL_TRIGGER_SESSION_STOP,
)

# ログ設定
logger = logging.getLogger(__name__)


class ECGSessionController:
    """
    ECGセッションの制御クラス
    """
    
    def __init__(
        self,
        feedback_mode: FeedbackMode,
        enable_logging: bool = True,
    ):
        """
        ECGSessionControllerの初期化
        
        Args:
            feedback_mode: フィードバックモードインスタンス
            enable_logging: ログ機能を有効にするかどうか（デフォルト: True）
        """
        self.feedback_mode = feedback_mode
        
        # ログ機能の設定（デフォルトで有効）
        self.enable_logging = enable_logging
        
        # ロガー
        self.beat_logger: Optional[BeatEventLogger] = None
        self.instantaneous_hr_logger: Optional[InstantaneousHRLogger] = None
        self.ecg_logger: Optional[ECGLogger] = None
        self.feedback_event_logger: Optional[FeedbackEventLogger] = None
        self.cognio_trigger_logger: Optional[CognioTriggerLogger] = None
        self.actichamp_trigger_logger: Optional[ActiChampTriggerLogger] = None
        
        # セッション状態（単純なフラグ）
        self.is_running = False
        
        # コンポーネント
        self.ecg_interface: Optional[ECGInterface] = None
        self.ecg_processor: Optional[ECGProcessor] = None
        self.cognio_trigger: Optional[CognioTrigger] = None
        self.actichamp_trigger: Optional[ActiChampTrigger] = None
        self.lsl_outlet: Optional[LSLOutlet] = None
        
        # フィードバックタイマー用のタスク
        self._feedback_task: Optional[asyncio.Task] = None
        
        # HR表示更新用のタスク（視覚FBモード用、200ms間隔）
        self._hr_display_task: Optional[asyncio.Task] = None
        
        # セッション自動終了タイマー用のタスク
        self._session_timer_task: Optional[asyncio.Task] = None
        
        logger.info(f"ECGSessionController initialized with mode: {type(feedback_mode).__name__}")
    
    async def start_session(self) -> bool:
        """
        ECGセッションを開始
        
        Returns:
            bool: 開始成功時True、失敗時False
        """
        if self.is_running:
            logger.warning("ECG session is already running")
            return False
        
        logger.info("Starting ECG session...")
        
        # ログ機能のセットアップ
        if self.enable_logging:
            self._setup_logging()
        
        # LSLアウトレットの初期化
        if ENABLE_LSL:
            self.lsl_outlet = LSLOutlet(
                stream_name=LSL_STREAM_NAME,
                stream_type="Markers",
                source_id="hr_biofeedback_marker"
            )
            if self.lsl_outlet.initialize():
                logger.info("LSL outlet initialized successfully")
            else:
                logger.warning("Failed to initialize LSL outlet, but continuing session")
                self.lsl_outlet = None
        
        # 順序2: トリガーの定義 - CognioTriggerインスタンス初期化・接続
        self.cognio_trigger = CognioTrigger()
        
        # Cognioトリガーロガーを設定（ログが有効な場合）
        if self.cognio_trigger_logger:
            self.cognio_trigger.trigger_logger = self.cognio_trigger_logger
            logger.info("CognioTriggerLogger assigned to CognioTrigger")
        
        if not await self.cognio_trigger.connect():
            logger.warning("Failed to connect to Cognio trigger, but continuing session")
            # トリガー接続失敗でもセッションは継続
        
        # ActiChampTriggerインスタンス初期化・接続
        self.actichamp_trigger = ActiChampTrigger()
        
        # ActiChampトリガーロガーを設定（ログが有効な場合）
        if self.actichamp_trigger_logger:
            self.actichamp_trigger.trigger_logger = self.actichamp_trigger_logger
            logger.info("ActiChampTriggerLogger assigned to ActiChampTrigger")
        
        if not await self.actichamp_trigger.connect():
            logger.warning("Failed to connect to actiCHamp trigger, but continuing session")
            # トリガー接続失敗でもセッションは継続
        
        # コンポーネントの初期化
        if not await self._initialize_components():
            return False
        
        # is_runningフラグを先に設定（create_taskで即座にループが実行される場合に備える）
        self.is_running = True
        
        # フィードバックタイマーの開始
        self._feedback_task = asyncio.create_task(self._feedback_timer_loop())
        
        # HR表示更新ループの開始（200ms間隔、視覚FBモード用）
        self._hr_display_task = asyncio.create_task(self._hr_display_loop())
        
        # セッション自動終了タイマーの開始
        self._session_timer_task = asyncio.create_task(self._session_timer())
        
        logger.info("ECG session started successfully")
        return True
    
    async def stop_session(self) -> None:
        """
        ECGセッションを停止
        """
        if not self.is_running:
            logger.warning("ECG session is not running")
            return
        
        logger.info("Stopping ECG session...")
        
        # セッション停止フラグを設定
        self.is_running = False
        
        # フィードバックタイマーの停止
        if self._feedback_task:
            self._feedback_task.cancel()
            try:
                await self._feedback_task
            except asyncio.CancelledError:
                pass
            self._feedback_task = None
        
        # HR表示更新ループの停止
        if self._hr_display_task:
            self._hr_display_task.cancel()
            try:
                await self._hr_display_task
            except asyncio.CancelledError:
                pass
            self._hr_display_task = None
        
        # セッション自動終了タイマーの停止
        if self._session_timer_task:
            self._session_timer_task.cancel()
            try:
                await self._session_timer_task
            except asyncio.CancelledError:
                pass
            self._session_timer_task = None
        
        # セッション終了フック（OCP準拠: 型チェックなし）
        self.feedback_mode.on_session_end()
        
        # ログ機能の終了
        if self.beat_logger:
            self.beat_logger.end_session()
            self.beat_logger = None
        
        if self.instantaneous_hr_logger:
            self.instantaneous_hr_logger.end_session()
            self.instantaneous_hr_logger = None
        
        if self.ecg_logger:
            self.ecg_logger.end_session()
            self.ecg_logger = None
        
        if self.feedback_event_logger:
            self.feedback_event_logger.end_session()
            self.feedback_event_logger = None
        
        # 順序5: ストリーミングを終了（コンポーネントのクリーンアップ）
        await self._cleanup_components()
        
        # 順序6: Cognioへ終了を示すトリガーパルスを送信
        if self.cognio_trigger:
            await self.cognio_trigger.send_trigger(COGNIO_TRIGGER, "Session_Stop")
            
            # Cognioトリガー接続をクローズ
            await self.cognio_trigger.disconnect()
            self.cognio_trigger = None
        
        # actiCHampへ終了を示すトリガーパルスを送信
        if self.actichamp_trigger:
            await self.actichamp_trigger.send_trigger(ACTICHAMP_TRIGGER, "Session_Stop")
            
            # ActiChampトリガー接続をクローズ
            await self.actichamp_trigger.disconnect()
            self.actichamp_trigger = None
        
        # LSL: トリガー送信後にセッション終了トリガーを送信
        if self.lsl_outlet and self.lsl_outlet.is_active:
            if self.lsl_outlet.send_trigger(LSL_TRIGGER_SESSION_STOP):
                logger.info(f"LSL session stop trigger ({LSL_TRIGGER_SESSION_STOP}) sent")
            else:
                logger.warning("Failed to send LSL session stop trigger")
        
        # LSLアウトレットのクローズ
        if self.lsl_outlet:
            self.lsl_outlet.close()
            self.lsl_outlet = None
        
        logger.info("ECG session stopped successfully")
    
    async def _initialize_components(self) -> bool:
        """
        各コンポーネントの初期化
        
        Returns:
            bool: 初期化成功時True
        """
        try:
            # ECGInterfaceの初期化
            self.ecg_interface = ECGInterface()
            
            # 接続試行
            if not await self.ecg_interface.connect():
                logger.error("Failed to connect to ECG device")
                return False
            
            # ECGProcessorの初期化
            self.ecg_processor = ECGProcessor()
            
            # ビート検出時のコールバック設定（ロギング用）
            self.ecg_processor.set_beat_callback(self._on_beat_detected)
            
            # 順序3: PolarにECGストリーミング開始コマンドを送信前にコールバック設定
            # 重要: start_notifyの前にコールバックを設定する必要がある
            self.ecg_interface.set_ecg_callback(self._on_ecg_data)
            
            # 順序4: PolarにECGストリーミング開始コマンドを送信
            if not await self.ecg_interface.start_ecg_streaming():
                logger.error("Failed to start ECG monitoring")
                return False
            
            # 順序5: Cognioへトリガーパルスを送信（ECGストリーミング開始）
            if self.cognio_trigger:
                trigger_sent = await self.cognio_trigger.send_trigger(COGNIO_TRIGGER, "Session_Start")
                if trigger_sent:
                    logger.info(f"ECG streaming start trigger pulse ({COGNIO_TRIGGER}→0) sent to Cognio")
                else:
                    logger.warning("Failed to send start trigger to Cognio, but continuing")
            
            # actiCHampへトリガーパルスを送信（EEGストリーミング開始）
            if self.actichamp_trigger:
                trigger_sent = await self.actichamp_trigger.send_trigger(ACTICHAMP_TRIGGER, "Session_Start")
            
            # LSL: トリガー送信後にセッション開始トリガーを送信
            if self.lsl_outlet and self.lsl_outlet.is_active:
                if self.lsl_outlet.send_trigger(LSL_TRIGGER_SESSION_START):
                    logger.info(f"LSL session start trigger ({LSL_TRIGGER_SESSION_START}) sent")
                else:
                    logger.warning("Failed to send LSL session start trigger")
            
            # 順序6: AudioFeedbackの初期化（ECG接続後）
            # pygame.mixerをここで初期化することで、COMスレッドモデルの競合を回避
            try:
                # AudioFeedbackにCognioトリガーとActiChampトリガーを設定
                if self.feedback_mode.audio_feedback is not None:
                    if self.cognio_trigger:
                        self.feedback_mode.audio_feedback.cognio_trigger = self.cognio_trigger
                        logger.info("CognioTrigger assigned to AudioFeedback for sound event triggers")
                    if self.actichamp_trigger:
                        self.feedback_mode.audio_feedback.actichamp_trigger = self.actichamp_trigger
                        logger.info("ActiChampTrigger assigned to AudioFeedback for sound event triggers")
                
                # FeedbackModeにLSLアウトレットを設定
                if self.lsl_outlet:
                    self.feedback_mode.lsl_outlet = self.lsl_outlet
                    logger.info("LSLOutlet assigned to FeedbackMode for LSL marker triggers")
                
                self.feedback_mode.initialize_audio()
            except Exception as e:
                logger.error(f"Failed to initialize AudioFeedback: {e}")
                # 音声フィードバックなしでも継続可能
            
            logger.info("All ECG components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"ECG component initialization failed: {e}")
            await self._cleanup_components()
            return False
    
    async def _cleanup_components(self) -> None:
        """
        コンポーネントのクリーンアップ
        """
        if self.ecg_interface:
            try:
                await self.ecg_interface.stop_ecg_streaming()
                await self.ecg_interface.disconnect()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
            finally:
                self.ecg_interface = None
        
        self.ecg_processor = None
        logger.info("ECG components cleaned up")
    
    async def _feedback_timer_loop(self) -> None:
        """
        5秒ごとのフィードバック処理ループ
        """
        import time
        
        while self.is_running:
            await asyncio.sleep(5.0)  # 5秒待機
            
            if self.is_running and self.ecg_processor:
                try:
                    # トレンド判定を取得
                    trend = self.ecg_processor.get_heart_rate_trend()
                    
                    # 5秒間の平均心拍数を計算（最新のECGタイムスタンプを基準に）
                    average_hr_bpm = self._calculate_average_hr()
                    
                    # フィードバック処理（音の種類を取得）
                    sound_type = self.feedback_mode.process_feedback(trend, average_hr_bpm)
                    
                    # ログ記録用にシステムタイムスタンプを取得
                    log_timestamp_ns = time.time_ns()
                    
                    # フィードバックイベントをログに記録
                    if self.feedback_event_logger:
                        # average_hr_bpmがNoneの場合は空文字列で記録
                        avg_hr_value = average_hr_bpm if average_hr_bpm is not None else ""
                        feedback_data = {
                            "timestamp_ns": log_timestamp_ns,
                            "average_hr_bpm": avg_hr_value,
                            "hr_trend": trend,
                            "sound_type": sound_type
                        }
                        self.feedback_event_logger.log_feedback(feedback_data)
                    
                    logger.info(f"Feedback processed: trend={trend}, avg_hr={average_hr_bpm}, sound={sound_type}")
                    
                except Exception as e:
                    logger.error(f"Error in feedback timer: {e}")
    
    async def _hr_display_loop(self) -> None:
        """
        200msごとに最新の瞬間心拍数を取得し、feedback_mode.on_hr_update()を呼ぶ。
        on_hr_update()のデフォルト実装は何もしないため、
        既存の聴覚FBモードには影響しない。
        """
        while self.is_running:
            await asyncio.sleep(0.2)
            if self.is_running and self.ecg_processor:
                try:
                    hr_data = self.ecg_processor.get_instantaneous_hr_data()
                    if hr_data:
                        _, latest_hr_bpm = hr_data[-1]
                        self.feedback_mode.on_hr_update(latest_hr_bpm)
                except Exception as e:
                    logger.error(f"_hr_display_loop でエラー: {e}")
    
    async def _session_timer(self) -> None:
        """
        セッション自動終了タイマー
        """

        duration = SESSION_DURATION_SECONDS
        
        try:
            # 設定時間のログ出力
            minutes = duration / 60.0
            logger.info(f"Session will automatically stop after {duration} seconds ({minutes:.1f} minutes)")
            
            # 設定時間待機
            await asyncio.sleep(duration)
            
            # 自動終了のログ出力
            if self.is_running:
                await self.stop_session()
                
        except asyncio.CancelledError:
            # 手動停止された場合
            logger.debug("Session timer cancelled (manual stop)")
            raise
        except Exception as e:
            logger.error(f"Error in session timer: {e}")
    
    def _calculate_average_hr(self) -> Optional[float]:
        """
        最新のECGタイムスタンプから直前5秒間の平均心拍数を計算
        
        Returns:
            Optional[float]: 5秒間の平均心拍数（BPM）、データがない場合はNone
        """
        if not self.ecg_processor or not self.ecg_processor.instantaneous_hr:
            return None
        
        # 瞬間心拍数データを取得
        all_hr_data = self.ecg_processor.instantaneous_hr.get_instantaneous_hr()
        
        if not all_hr_data:
            return None
        
        # 最新のタイムスタンプを取得（ECGデバイスのタイムスタンプ基準）
        latest_timestamp_ns = all_hr_data[-1][0]
        
        # 5秒間の窓を設定
        window_ns = int(5.0 * 1_000_000_000)
        start_time_ns = latest_timestamp_ns - window_ns
        
        # 直前5秒間の瞬間心拍数データをフィルタリング
        hr_data = [
            hr for ts, hr in all_hr_data
            if start_time_ns < ts <= latest_timestamp_ns
        ]
        
        # データがあれば平均を計算
        if hr_data:
            import numpy as np
            return float(np.mean(hr_data))
        
        return None
    
    def _on_ecg_data(self, ecg_data: dict) -> None:
        """
        ECGデータ受信時のコールバック
        
        Args:
            ecg_data: ECGデータ（{"ecg_samples": List[float], "timestamps": List[int]}）
        """
        try:
            # データ処理
            if self.ecg_processor:
                self.ecg_processor.add_ecg_data(ecg_data)
            
            # ECGログ機能: ECGデータをCSVファイルに保存
            if self.ecg_logger:
                self.ecg_logger.log_ecg(ecg_data)
            
            # Beat/InstantaneousHRのロギングは _on_beat_detected で実行
            # （ECGProcessorの内部コールバックから呼び出される想定）
            
        except Exception as e:
            logger.error(f"Error processing ECG data: {e}")
    
    def _on_beat_detected(self, beat_event: BeatEvent) -> None:
        """
        R波検出時のコールバック（ロギング用）
        
        Args:
            beat_event (BeatEvent): 検出されたR波イベント
        """
        try:
            # BeatEventLoggerでロギング
            if self.beat_logger:
                beat_data = {
                    "timestamp_ns": beat_event.timestamp_ns,
                    "sample_index": beat_event.sample_index,
                    "amplitude": beat_event.amplitude,
                    "rr_interval_ms": beat_event.rr_interval_ms
                }
                self.beat_logger.log_beat(beat_data)
            
            # RR間隔が有効な場合のみInstantaneousHRLoggerでロギング
            if self.instantaneous_hr_logger and beat_event.rr_interval_ms is not None:
                instantaneous_hr_bpm = 60000.0 / beat_event.rr_interval_ms
                instantaneous_hr_data = {
                    "timestamp_ns": beat_event.timestamp_ns,
                    "rr_interval_ms": beat_event.rr_interval_ms,
                    "instantaneous_hr_bpm": instantaneous_hr_bpm
                }
                self.instantaneous_hr_logger.log_instantaneous_hr(instantaneous_hr_data)
                
        except Exception as e:
            logger.error(f"Error in beat detected callback: {e}")
    
    def _setup_logging(self) -> None:
        """
        ログ機能のセットアップ
        """
        if not self.enable_logging:
            return
        
        try:
            # BeatEventLoggerの初期化（デフォルト: ecg_config.BEAT_LOG_DIRECTORY）
            self.beat_logger = BeatEventLogger()
            self.beat_logger.start_session()
            logger.info(f"Beat logging enabled: {self.beat_logger.get_filename()}")
            
            # InstantaneousHRLoggerの初期化（デフォルト: ecg_config.INSTANTANEOUS_HR_LOG_DIRECTORY）
            self.instantaneous_hr_logger = InstantaneousHRLogger()
            self.instantaneous_hr_logger.start_session()
            logger.info(f"Instantaneous HR logging enabled: {self.instantaneous_hr_logger.get_filename()}")
            
            # ECGLoggerの初期化（デフォルト: ecg_config.ECG_LOG_DIRECTORY）
            self.ecg_logger = ECGLogger()
            self.ecg_logger.start_session()
            logger.info(f"ECG logging enabled: {self.ecg_logger.get_filename()}")
            
            # FeedbackEventLoggerの初期化（デフォルト: ecg_config.FEEDBACK_EVENT_LOG_DIRECTORY）
            self.feedback_event_logger = FeedbackEventLogger()
            self.feedback_event_logger.start_session()
            logger.info(f"Feedback event logging enabled: {self.feedback_event_logger.get_filename()}")
            
            # CognioTriggerLoggerの初期化（デフォルト: ecg_config.COGNIO_TRIGGER_LOG_DIRECTORY）
            self.cognio_trigger_logger = CognioTriggerLogger()
            self.cognio_trigger_logger.start_session()
            logger.info(f"Cognio trigger logging enabled: {self.cognio_trigger_logger.get_filename()}")
            
            # ActiChampTriggerLoggerの初期化（デフォルト: ecg_config.ACTICHAMP_TRIGGER_LOG_DIRECTORY）
            self.actichamp_trigger_logger = ActiChampTriggerLogger()
            self.actichamp_trigger_logger.start_session()
            logger.info(f"actiCHamp trigger logging enabled: {self.actichamp_trigger_logger.get_filename()}")
            
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}")
            # エラーが発生してもセッションは継続可能
            self.beat_logger = None
            self.instantaneous_hr_logger = None
            self.ecg_logger = None
            self.feedback_event_logger = None
            self.actichamp_trigger_logger = None

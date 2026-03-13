"""
ECG心拍バイオフィードバック実験プログラム - メインアプリケーション

使用例:
    python src/ecg_main.py --mode increase    # 心拍数増加報酬モード
    python src/ecg_main.py --mode decrease    # 心拍数減少報酬モード
    python src/ecg_main.py --mode random      # ランダムモード(対照群)
"""
import asyncio
import argparse
import signal
import logging
import sys
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.session.ecg_session_controller import ECGSessionController
from src.feedback.audio_feedback import AudioFeedback
from src.feedback.feedback_modes import IncreaseRewardMode, DecreaseRewardMode, RandomMode

# ログ設定
# 解説: アプリケーションの実行ログを標準出力とファイルの両方に記録
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ecg_session.log')  # ECG専用ログファイル
    ]
)
logger = logging.getLogger(__name__)


class ECGBiofeedbackApp:
    """
    ECG心拍バイオフィードバックアプリケーションクラス
    """
    
    def __init__(self):
        """
        アプリケーションの初期化
        """
        self.session_controller = None
        self.shutdown_event = asyncio.Event()
        
    def create_feedback_mode(self, mode_name: str):
        """
        フィードバックモードを作成
        
        Args:
            mode_name: フィードバックモード名 ("increase", "decrease", "random")
            
        Returns:
            FeedbackMode: 選択されたフィードバックモード
            
        Raises:
            ValueError: 無効なモード名の場合
        """
        try:
            # 音声ファイルのパスを設定
            project_root = Path(__file__).parent.parent
            high_sound = str(project_root / "assets" / "audio" / "high_sound.wav")
            low_sound = str(project_root / "assets" / "audio" / "low_sound.wav")
            
            # AudioFeedbackの初期化
            audio_feedback = AudioFeedback(high_sound, low_sound)
            
            # モードに応じたフィードバッククラスを作成
            mode_map = {
                "increase": IncreaseRewardMode,
                "decrease": DecreaseRewardMode,
                "random": RandomMode
            }
            
            if mode_name not in mode_map:
                raise ValueError(f"Invalid feedback mode: {mode_name}")
            
            feedback_mode = mode_map[mode_name](audio_feedback)
            logger.info(f"Created feedback mode: {mode_name}")
            return feedback_mode
            
        except Exception as e:
            logger.error(f"Failed to create feedback mode: {e}")
            raise
    
    def setup_signal_handlers(self):
        """
        シグナルハンドラーの設定

        機能:
        - SIGINT: Ctrl+Cによる中断
        - SIGTERM: システムからの終了要求
        これらのシグナルを受信したときに、適切にシャットダウン処理を実行
        """
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        # Ctrl+C (SIGINT) とTERM信号をハンドル
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Signal handlers configured")
    
    async def shutdown(self):
        """
        アプリケーションのシャットダウン
        
        処理フロー:
        1. 実行中のセッションを停止
        2. ECGデバイスとの接続を切断
        3. ログファイルを適切にクローズ
        """
        logger.info("Shutting down application...")
        
        if self.session_controller and self.session_controller.is_running:
            logger.info("Session manually stopped by user")
            await self.session_controller.stop_session()
        
        self.shutdown_event.set()
        logger.info("Application shutdown complete")
    
    def parse_arguments(self):
        """
        コマンドライン引数の解析
        
        Returns:
            argparse.Namespace: 解析された引数
        """
        parser = argparse.ArgumentParser(
            description='ECG心拍バイオフィードバック実験プログラム',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  %(prog)s --mode increase     心拍数増加で報酬音を再生
  %(prog)s --mode decrease     心拍数減少で報酬音を再生
  %(prog)s --mode random       ランダムに報酬音を再生（対照群）
  """
        )
        
        parser.add_argument(
            '--mode',
            choices=['increase', 'decrease', 'random'],
            required=True,
            help='フィードバックモード (increase/decrease/random)'
        )
        
        return parser.parse_args()
    
    async def run(self):
        """
        アプリケーションのメイン実行
        
        処理フロー:
        1. コマンドライン引数の解析
        2. ログレベルの設定
        3. シグナルハンドラーの設定
        4. フィードバックモードの作成
        5. ECGSessionControllerの初期化
        6. ECGセッションの開始
        7. ユーザーによる中断まで待機
        8. 適切なシャットダウン処理
        """
        try:
            # コマンドライン引数の解析
            args = self.parse_arguments()
            
            # シグナルハンドラーの設定
            self.setup_signal_handlers()
            
            # フィードバックモードの作成
            feedback_mode = self.create_feedback_mode(args.mode)
            
            # ECGSessionControllerの初期化
            self.session_controller = ECGSessionController(
                feedback_mode=feedback_mode,
                enable_logging=True,      # ロギング機能を有効化（デフォルト）
            )
            
            logger.info(f"Starting ECG session with mode: {args.mode}")
            
            # セッション開始
            start_success = await self.session_controller.start_session()
            
            if not start_success:
                logger.error("Failed to start ECG session")
                return 1
            
            logger.info("ECG session started - monitoring ECG data and heart rate trends")
            logger.info("Feedback will be provided every 5 seconds based on heart rate trend")
            logger.info("Press Ctrl+C to stop manually")
            
            # シャットダウンまで待機
            await self.shutdown_event.wait()
            
            return 0
            
        except KeyboardInterrupt:
            logger.info("User interrupted")
            await self.shutdown()
            return 0
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            await self.shutdown()
            return 1


async def main():
    """
    メイン関数
    
    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    app = ECGBiofeedbackApp()
    return await app.run()


def main_sync():
    """
    同期版メイン関数（エントリーポイント用）
    
    Returns:
        int: 終了コード
    """
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main_sync()
    sys.exit(exit_code)

"""
視覚フィードバック + 金銭的報酬モード エントリーポイント

使用例:
    python -m src.visual_main --mode visual_monetary
    python src/visual_main.py

スレッド構成:
    メインスレッド: Tkinter mainloop() （メインスレッド必須）
    asyncio スレッド: ECG セッション制御

注意: signal.signal() はメインスレッドで呼ぶこと。
"""
import asyncio
import threading
import signal
import logging
import sys
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.session.ecg_session_controller import ECGSessionController
from src.feedback.visual_monetary_feedback import VisualMonetaryFeedback
from src.feedback.visual_feedback_gui import VisualFeedbackGUI
from src.logger.visual_reward_logger import VisualRewardLogger
from src.config.ecg_config import (
    REWARD_RATE_YEN_PER_SEC,
    SHAPING_STEP_BPM,
    SESSION_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)


def run_visual_monetary() -> None:
    """
    visual_monetary モードの起動フロー。

    1. GUI インスタンスを生成（まだ mainloop は開始しない）
    2. asyncio ループを別スレッドで起動
    3. メインスレッドで GUI.start()（mainloop に入る）
    4. mainloop が return したらプロセス終了
    """
    asyncio_loop = asyncio.new_event_loop()
    shutdown_event = threading.Event()  # スレッドセーフな Event

    # session_controller を格納する変数（signal_handler からアクセス可能にする）
    session_controller_holder: list = [None]

    # shutdown コールバック（GUI × ボタンから呼ばれる）
    def shutdown_callback() -> None:
        sc = session_controller_holder[0]
        if sc is not None:
            asyncio.run_coroutine_threadsafe(
                _shutdown(sc, shutdown_event), asyncio_loop
            )

    # GUI 生成
    gui = VisualFeedbackGUI(
        session_duration_seconds=SESSION_DURATION_SECONDS,
        shutdown_callback=shutdown_callback,
    )

    # feedback_mode 生成
    visual_reward_logger = VisualRewardLogger()
    visual_reward_logger.start_session()

    feedback_mode = VisualMonetaryFeedback(
        gui=gui,
        reward_rate_yen_per_sec=REWARD_RATE_YEN_PER_SEC,
        shaping_step_bpm=SHAPING_STEP_BPM,
        visual_reward_logger=visual_reward_logger,
    )

    # session_controller 生成
    session_controller = ECGSessionController(
        feedback_mode=feedback_mode,
        enable_logging=True,
    )
    session_controller_holder[0] = session_controller

    # シグナルハンドラ（メインスレッドで呼ぶこと）
    def signal_handler(signum: int, frame) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.run_coroutine_threadsafe(
            _shutdown(session_controller, shutdown_event), asyncio_loop
        )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # asyncio スレッド起動
    def asyncio_thread() -> None:
        asyncio.set_event_loop(asyncio_loop)
        asyncio_loop.run_until_complete(
            _run_session(session_controller, shutdown_event, gui)
        )
        asyncio_loop.close()

    t = threading.Thread(target=asyncio_thread, daemon=True)
    t.start()

    # メインスレッドで GUI 起動（ここで mainloop に入る）
    gui.start()

    # mainloop が return したら asyncio スレッドの終了を待つ
    shutdown_event.set()  # asyncio 側にも終了を通知
    t.join(timeout=5.0)


async def _run_session(
    session_controller: ECGSessionController,
    shutdown_event: threading.Event,
    gui: VisualFeedbackGUI,
) -> None:
    """asyncio スレッド内で実行するセッション処理。"""
    start_success = await session_controller.start_session()
    if not start_success:
        logger.error("セッション開始失敗")
        # GUI に失敗を通知（GUI が永久に待つのを防ぐ）
        gui.enqueue_session_end(0.0)
        shutdown_event.set()
        return

    logger.info("Visual monetary session started")

    # threading.Event を asyncio 内で await する
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, shutdown_event.wait)

    # shutdown_event が set された後、pending タスクの完了を待つ
    # （stop_session() が _session_timer 内で実行中の可能性があるため）
    pending = [
        t for t in asyncio.all_tasks(loop)
        if t is not asyncio.current_task() and not t.done()
    ]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _shutdown(
    session_controller: ECGSessionController,
    shutdown_event: threading.Event,
) -> None:
    """セッションを停止する。"""
    if session_controller and session_controller.is_running:
        await session_controller.stop_session()
    shutdown_event.set()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("ecg_session.log"),
        ],
    )
    run_visual_monetary()

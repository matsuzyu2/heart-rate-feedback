"""
視覚フィードバック + 金銭的報酬モード

McCanne & Sandman (1975) に基づく金銭報酬先行設計。
プロポーショナル型視覚 FB（HR ゲージ）との組み合わせで実装する。
"""
import time
import logging
from typing import Optional, TYPE_CHECKING

from .feedback_modes import FeedbackMode
from ..config.ecg_config import HR_BLOCK_WINDOW_SECONDS

if TYPE_CHECKING:
    from .visual_feedback_gui import VisualFeedbackGUI
    from ..logger.visual_reward_logger import VisualRewardLogger

logger = logging.getLogger(__name__)


class VisualMonetaryFeedback(FeedbackMode):
    """
    視覚フィードバック + 金銭的報酬モード

    プロポーショナル型 HR ゲージとシェイピングベースの金銭的報酬を組み合わせる。
    音声フィードバックは使用しない。
    """

    def __init__(
        self,
        gui: "VisualFeedbackGUI",
        reward_rate_yen_per_sec: float,
        shaping_step_bpm: float,
        visual_reward_logger: "VisualRewardLogger",
    ):
        """
        視覚フィードバックモードの初期化

        Args:
            gui: 視覚フィードバック GUI インスタンス
            reward_rate_yen_per_sec: 報酬レート（円/秒）
            shaping_step_bpm: シェイピング基準の増減幅（BPM）
            visual_reward_logger: 報酬ログ記録用ロガー
        """
        super().__init__(audio_feedback=None)  # 音声なし
        self.gui = gui
        self.reward_rate_yen_per_sec = reward_rate_yen_per_sec
        self.shaping_step_bpm = shaping_step_bpm
        self.visual_reward_logger = visual_reward_logger

        # 内部状態
        self.baseline_hr_bpm: Optional[float] = None
        self.current_criterion_bpm: Optional[float] = None
        self.accumulated_reward_yen: float = 0.0
        self.is_on_target: bool = False
        self._consecutive_hits: int = 0
        self._consecutive_miss: int = 0
        self._last_hr_bpm: Optional[float] = None

    def process_feedback(self, trend: str, average_hr_bpm: float = None) -> str:
        """
        5秒ごとに呼ばれるフィードバック処理。
        シェイピングと報酬加算を行う。

        Args:
            trend: "increasing" / "decreasing" / "stable"
            average_hr_bpm: 直前5秒の平均 HR（BPM）

        Returns:
            str: "on_target" / "off_target" / "none"

        Note:
            戻り値は既存の聴覚モードの "high" / "low" / "none" とは異なる。
            feedback_event_logger の sound_type カラムにこれらの値が記録される。
        """
        # ステップ1: ベースライン初期化（初回のみ）
        if self.baseline_hr_bpm is None:
            if average_hr_bpm is None:
                return "none"
            self.baseline_hr_bpm = average_hr_bpm
            self.current_criterion_bpm = average_hr_bpm + self.shaping_step_bpm
            logger.info(
                f"ベースライン設定: {self.baseline_hr_bpm:.1f} BPM, "
                f"初期基準: {self.current_criterion_bpm:.1f} BPM"
            )
            return "none"

        # 信号ロスト時は "none" を返す（"off_target" と区別するため）
        if average_hr_bpm is None:
            return "none"

        # ステップ2: 基準達成判定
        is_on_target = average_hr_bpm >= self.current_criterion_bpm

        # ステップ3: 報酬加算
        reward_delta = 0.0
        if is_on_target:
            reward_delta = HR_BLOCK_WINDOW_SECONDS * self.reward_rate_yen_per_sec
            self.accumulated_reward_yen += reward_delta
        self.is_on_target = is_on_target

        # ステップ4: シェイピング更新
        self._update_shaping(is_on_target)

        # ステップ5: ログ記録
        self.visual_reward_logger.log_reward_event({
            "timestamp_ns": time.time_ns(),
            "current_hr_bpm": average_hr_bpm,
            "criterion_hr_bpm": self.current_criterion_bpm,
            "is_on_target": is_on_target,
            "reward_delta_yen": reward_delta,
            "accumulated_reward_yen": self.accumulated_reward_yen,
        })

        return "on_target" if is_on_target else "off_target"

    def _update_shaping(self, is_on_target: bool) -> None:
        """
        シェイピング基準を更新する。

        ルール（McCanne & Sandman 簡易版）:
          3 ブロック連続達成（15 秒）→ 基準を shaping_step_bpm 引き上げ
          3 ブロック連続未達（15 秒）→ 基準を shaping_step_bpm 引き下げ（下限: baseline）

        重要: 達成/未達が切り替わった際はカウンターを両方リセットする。
        """
        CONSECUTIVE_THRESHOLD = 3

        if is_on_target:
            self._consecutive_hits += 1
            self._consecutive_miss = 0
        else:
            self._consecutive_miss += 1
            self._consecutive_hits = 0

        if self._consecutive_hits >= CONSECUTIVE_THRESHOLD:
            self.current_criterion_bpm += self.shaping_step_bpm
            self._consecutive_hits = 0
            logger.info(
                f"シェイピング: 基準を引き上げ → {self.current_criterion_bpm:.1f} BPM"
            )
        elif self._consecutive_miss >= CONSECUTIVE_THRESHOLD:
            self.current_criterion_bpm = max(
                self.baseline_hr_bpm,
                self.current_criterion_bpm - self.shaping_step_bpm,
            )
            self._consecutive_miss = 0
            logger.info(
                f"シェイピング: 基準を引き下げ → {self.current_criterion_bpm:.1f} BPM"
            )

    def on_hr_update(self, current_hr_bpm: float) -> None:
        """200ms ごとに呼ばれる。GUI Queue に最新状態を push する。"""
        self._last_hr_bpm = current_hr_bpm
        if self.current_criterion_bpm is None:
            return  # ベースライン未設定なら何もしない
        self.gui.enqueue_state({
            "current_hr_bpm": current_hr_bpm,
            "criterion_hr_bpm": self.current_criterion_bpm,
            "accumulated_reward_yen": self.accumulated_reward_yen,
            "is_on_target": self.is_on_target,
        })

    def on_session_end(self) -> None:
        """セッション終了を GUI に通知し、ロガーを終了する。"""
        self.gui.enqueue_session_end(self.accumulated_reward_yen)
        self.visual_reward_logger.end_session()

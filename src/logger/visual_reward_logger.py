"""
VisualRewardLoggerクラス - 視覚FB報酬データのCSV保存機能
"""
import csv
from typing import Dict, Any, List

from .base_logger import BaseSessionLogger
from ..config.ecg_config import VISUAL_REWARD_LOG_DIRECTORY


class VisualRewardLogger(BaseSessionLogger):
    """
    視覚FB報酬データをCSVファイルに保存するクラス

    CSVフォーマット:
        timestamp_ns: 報酬イベント時刻（ナノ秒）
        current_hr_bpm: 現在の平均心拍数（BPM）
        criterion_hr_bpm: 基準心拍数（BPM）
        is_on_target: 基準達成フラグ（True/False）
        reward_delta_yen: 今回の報酬加算額（円）
        accumulated_reward_yen: 累積報酬額（円）
    """

    # CSVカラム定義
    COLUMNS = [
        'timestamp_ns',
        'current_hr_bpm',
        'criterion_hr_bpm',
        'is_on_target',
        'reward_delta_yen',
        'accumulated_reward_yen',
    ]

    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す

        Returns:
            str: VISUAL_REWARD_LOG_DIRECTORYのパス
        """
        return VISUAL_REWARD_LOG_DIRECTORY

    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す

        Returns:
            str: "visual_reward"
        """
        return "visual_reward"

    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す

        Returns:
            List[str]: VisualRewardデータのカラム名
        """
        return self.COLUMNS

    def log_reward_event(self, data: Dict[str, Any]) -> None:
        """
        報酬イベントデータをCSVファイルに追記保存

        Args:
            data (Dict[str, Any]): 報酬イベントデータ
                キー: timestamp_ns, current_hr_bpm, criterion_hr_bpm,
                      is_on_target, reward_delta_yen, accumulated_reward_yen

        Raises:
            KeyError: 必須フィールドが欠落している場合
        """
        # 必須フィールドの存在確認
        for field in self.COLUMNS:
            if field not in data:
                raise KeyError(f"'{field}' field is required")

        # 報酬イベントデータを1行として保存
        with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([data[col] for col in self.COLUMNS])

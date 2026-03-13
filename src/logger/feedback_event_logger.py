"""
FeedbackEventLoggerクラス - フィードバックイベントデータのCSV保存機能
"""
import csv
from typing import Dict, Any, List

from .base_logger import BaseSessionLogger
from ..config.ecg_config import FEEDBACK_EVENT_LOG_DIRECTORY


class FeedbackEventLogger(BaseSessionLogger):
    """
    フィードバックイベントデータをCSVファイルに保存するクラス
    
    CSVフォーマット:
        timestamp_ns: フィードバック処理時刻（ナノ秒）
        average_hr_bpm: 5秒間の平均心拍数（BPM）
        hr_trend: 心拍数の変化方向 ("increasing", "decreasing", "stable")
        sound_type: 再生された音 ("high", "low", "none")
    """
    
    # CSVカラム定義
    COLUMNS = ['timestamp_ns', 'average_hr_bpm', 'hr_trend', 'sound_type']
    
    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す
        
        Returns:
            str: FEEDBACK_EVENT_LOG_DIRECTORYのパス
        """
        return FEEDBACK_EVENT_LOG_DIRECTORY
    
    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す
        
        Returns:
            str: "feedback_event"
        """
        return "feedback_event"
    
    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す
        
        Returns:
            List[str]: FeedbackEventデータのカラム名
        """
        return self.COLUMNS
    
    def log_feedback(self, feedback_event: Dict[str, Any]) -> None:
        """
        フィードバックイベントデータをCSVファイルに追記保存
        
        Args:
            feedback_event (Dict[str, Any]): フィードバックイベントデータ
            
        Raises:
            KeyError: 必須フィールドが欠落している場合
        """
        # 必須フィールドの存在確認
        required_fields = ['timestamp_ns', 'average_hr_bpm', 'hr_trend', 'sound_type']
        for field in required_fields:
            if field not in feedback_event:
                raise KeyError(f"'{field}' field is required")
        
        # 各フィールドの値を取得
        timestamp_ns = feedback_event['timestamp_ns']
        average_hr_bpm = feedback_event['average_hr_bpm']
        hr_trend = feedback_event['hr_trend']
        sound_type = feedback_event['sound_type']
        
        # フィードバックイベントデータを1行として保存
        with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp_ns,
                average_hr_bpm,
                hr_trend,
                sound_type
            ])

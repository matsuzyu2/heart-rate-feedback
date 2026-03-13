"""
CognioTriggerLoggerクラス - Cognioトリガー送信イベントのCSV保存機能
"""
import csv
from typing import List
from datetime import datetime

from .base_logger import BaseSessionLogger
from ..config.ecg_config import COGNIO_TRIGGER_LOG_DIRECTORY


class CognioTriggerLogger(BaseSessionLogger):
    """
    CognioトリガーイベントをCSVファイルに保存するクラス
    
    CSVフォーマット:
        timestamp: トリガー送信時刻（ISO 8601形式）
        trigger_value: 送信されたトリガー値
        annotation: イベントの説明（Session_Start, Session_Stop, Feedback_High, Feedback_Low）
    """
    
    # CSVカラム定義
    COLUMNS = ['timestamp', 'trigger_value', 'annotation']
    
    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す
        
        Returns:
            str: COGNIO_TRIGGER_LOG_DIRECTORYのパス
        """
        return COGNIO_TRIGGER_LOG_DIRECTORY
    
    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す
        
        Returns:
            str: "cognio_trigger"
        """
        return "cognio_trigger"
    
    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す
        
        Returns:
            List[str]: CognioTriggerデータのカラム名
        """
        return self.COLUMNS
    
    def log_trigger(self, trigger_value: int, annotation: str) -> None:
        """
        CognioトリガーイベントをCSVファイルに追記保存
        
        Args:
            trigger_value (int): 送信されたトリガー値
            annotation (str): イベントの説明（例: "Session_Start", "Feedback_High"）
        """
        # 現在時刻を取得（ISO 8601形式）
        timestamp = datetime.now().isoformat()
        
        # トリガーイベントデータを1行として保存
        with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                trigger_value,
                annotation
            ])

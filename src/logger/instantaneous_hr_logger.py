"""
InstantaneousHRLoggerクラス - 瞬間心拍数データのCSV保存機能
"""
import csv
from typing import Dict, Any, List

from .base_logger import BaseSessionLogger
from ..config.ecg_config import INSTANTANEOUS_HR_LOG_DIRECTORY


class InstantaneousHRLogger(BaseSessionLogger):
    """
    瞬間心拍数データをCSVファイルに保存するクラス
    
    CSVフォーマット:
        id: 連番ID（1から開始）
        timestamp_ns: 心拍発生時刻（ナノ秒）
        rr_interval_ms: R-R間隔（ミリ秒）
        instantaneous_hr_bpm: 瞬間心拍数（bpm）
    
    """
    
    # CSVカラム定義
    COLUMNS = ['id', 'timestamp_ns', 'rr_interval_ms', 'instantaneous_hr_bpm']
    
    def __init__(self):
        """
        InstantaneousHRLoggerを初期化
        """
        super().__init__()
        self._record_id = 0  # 連番IDカウンタ（1から始まる）
    
    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す
        
        Returns:
            str: INSTANTANEOUS_HR_LOG_DIRECTORYのパス
        """
        return INSTANTANEOUS_HR_LOG_DIRECTORY
    
    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す
        
        Returns:
            str: "instantaneous_hr"
        """
        return "instantaneous_hr"
    
    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す
        
        Returns:
            List[str]: 瞬間心拍数データのカラム名
        """
        return self.COLUMNS
    
    def end_session(self) -> None:
        """
        セッションを終了
        """
        super().end_session()
        self._record_id = 0  # IDカウンタをリセット
    
    def log_instantaneous_hr(self, instantaneous_hr_data: Dict[str, Any]) -> None:
        """
        瞬間心拍数データをCSVファイルに追記保存
        
        Args:
            instantaneous_hr_data (Dict[str, Any]): 瞬間心拍数データ
                必須フィールド: 'timestamp_ns', 'rr_interval_ms', 'instantaneous_hr_bpm'
                
        Raises:
            KeyError: 必須フィールドが欠落している場合
        """
        # 必須フィールドの存在確認
        required_fields = ['timestamp_ns', 'rr_interval_ms', 'instantaneous_hr_bpm']
        for field in required_fields:
            if field not in instantaneous_hr_data:
                raise KeyError(f"'{field}' field is required")
        
        # 連番IDをインクリメント（1から始まる）
        self._record_id += 1
        
        # 各フィールドの値を取得
        timestamp_ns = instantaneous_hr_data['timestamp_ns']
        rr_interval_ms = instantaneous_hr_data['rr_interval_ms']
        instantaneous_hr_bpm = instantaneous_hr_data['instantaneous_hr_bpm']
        
        # 瞬間心拍数データを1行として保存
        with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                self._record_id,
                timestamp_ns,
                rr_interval_ms,
                instantaneous_hr_bpm
            ])

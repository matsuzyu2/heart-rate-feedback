"""
ECGLoggerクラス - ECGサンプルデータのCSV保存機能
"""
import csv
from typing import Dict, Any, List

from .base_logger import BaseSessionLogger
from ..config.ecg_config import ECG_LOG_DIRECTORY


class ECGLogger(BaseSessionLogger):
    """
    ECGデータをCSVファイルに保存するクラス
    
    CSVフォーマット:
        timestamp_ns: サンプル取得時刻（ナノ秒）
        ecg_value_μv: ECG値（マイクロボルト）
    """
    
    # CSVカラム定義
    COLUMNS = ['timestamp_ns', 'ecg_value_μv']
    
    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す
        
        Returns:
            str: ECG_LOG_DIRECTORYのパス
        """
        return ECG_LOG_DIRECTORY
    
    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す
        
        Returns:
            str: "ecg"
        """
        return "ecg"
    
    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す
        
        Returns:
            List[str]: ECGデータのカラム名
        """
        return self.COLUMNS
    
    def log_ecg_data(self, ecg_data: Dict[str, Any]) -> None:
        """
        ECGデータをCSVファイルに追記保存
        
        Args:
            ecg_data (Dict[str, Any]): ECGデータ
                必須フィールド: 'ecg_samples', 'timestamps'
                
        Raises:
            KeyError: 必須フィールドが欠落している場合
            ValueError: データ長が一致しない場合
        """
        # 必須フィールドの存在確認
        required_fields = ['ecg_samples', 'timestamps']
        for field in required_fields:
            if field not in ecg_data:
                raise KeyError(f"'{field}' field is required")
        
        ecg_samples = ecg_data['ecg_samples']
        timestamps = ecg_data['timestamps']
        
        # データ長の整合性確認
        if len(ecg_samples) != len(timestamps):
            raise ValueError(
                f"Length mismatch: ecg_samples({len(ecg_samples)}) "
                f"!= timestamps({len(timestamps)})"
            )
        
        # 各ECGサンプルを個別行として保存
        with open(self.file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for ecg_value, timestamp_ns in zip(ecg_samples, timestamps):
                writer.writerow([timestamp_ns, ecg_value])
    
    def log_multiple_ecg_data(self, ecg_data_list: List[Dict[str, Any]]) -> None:
        """
        複数のECGデータを一括でCSVファイルに追記保存
        
        Args:
            ecg_data_list (List[Dict[str, Any]]): ECGデータのリスト
        """
        for ecg_data in ecg_data_list:
            self.log_ecg_data(ecg_data)
    
    def log_ecg(self, ecg_data: Dict[str, Any]) -> None:
        """
        ECGデータをCSVファイルに追記保存（log_ecg_dataのエイリアス）
        
        Args:
            ecg_data (Dict[str, Any]): ECGデータ
                必須フィールド: 'ecg_samples', 'timestamps'
        """
        self.log_ecg_data(ecg_data)

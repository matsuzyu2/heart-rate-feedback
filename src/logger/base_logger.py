"""
BaseSessionLogger - セッションベースのCSVロギング抽象基底クラス

このモジュールは、Template Methodパターンを使用して、全てのLoggerクラスに
共通するセッション管理とCSVファイル操作の機能を提供します。
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import csv
import os
from datetime import datetime


class BaseSessionLogger(ABC):
    """
    CSV形式のセッションログを管理する抽象基底クラス
    
    Attributes:
        output_dir (str): ログファイルの出力先ディレクトリ
        file_path (Optional[str]): 現在のセッションのログファイルパス
        _session_started (bool): セッション開始状態のフラグ
    """
    
    def __init__(self):
        """
        BaseSessionLoggerを初期化
        """
        self.output_dir = self._get_log_directory()
        self.file_path: Optional[str] = None
        self._session_started = False
    
    @abstractmethod
    def _get_log_directory(self) -> str:
        """
        ログディレクトリのパスを返す
        
        Returns:
            str: ログファイルを保存するディレクトリの絶対パス
        """
        pass
    
    @abstractmethod
    def _get_file_prefix(self) -> str:
        """
        ファイル名のプレフィックスを返す
        
        サブクラスで実装必須。タイムスタンプ付きファイル名の一部として使用されます。
        
        Returns:
            str: ファイル名のプレフィックス (例: "ecg", "beat", "instantaneous_hr")
        """
        pass
    
    @abstractmethod
    def _get_csv_columns(self) -> List[str]:
        """
        CSVのカラム名リストを返す
        
        サブクラスで実装必須。CSVヘッダー行として書き込まれます。
        
        Returns:
            List[str]: CSVカラム名のリスト
        """
        pass
    
    def start_session(self) -> str:
        """
        セッションを開始し、タイムスタンプ付きファイル名を生成
        
        このメソッドは以下の処理を実行します:
        1. セッション開始状態のチェック
        2. タイムスタンプ付きファイル名の生成
        3. CSVファイルの初期化（ヘッダー書き込み）
        4. セッション状態の更新
        
        Returns:
            str: 生成されたファイルの完全パス
            
        Raises:
            RuntimeError: セッションが既に開始されている場合
        """
        if self._session_started:
            raise RuntimeError("Session already started")
        
        # タイムスタンプ付きファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self._get_file_prefix()}_session.csv"
        self.file_path = os.path.join(self.output_dir, filename)
        
        # CSVファイルを初期化
        self._initialize_csv_file()
        self._session_started = True
        
        return self.file_path
    
    def end_session(self) -> None:
        """
        セッションを終了
        
        現在のセッションを終了し、状態をリセットします。
        サブクラスでクリーンアップ処理が必要な場合は、このメソッドをオーバーライドできます。
        """
        if not self._session_started:
            return
        
        self._session_started = False
        # 将来的にクリーンアップ処理を追加する場合はここに記述
    
    def get_filename(self) -> str:
        """
        現在のログファイル名を取得
        
        Returns:
            str: ログファイルの完全パス
            
        Raises:
            RuntimeError: セッションが開始されていない場合
        """
        if self.file_path is None:
            raise RuntimeError("Session not started. Call start_session() first.")
        return self.file_path
    
    def _initialize_csv_file(self) -> None:
        """
        CSVファイルを初期化してヘッダーを書き込む
        
        このメソッドは以下の処理を実行します:
        1. 必要に応じて親ディレクトリを作成
        2. ファイルが存在しない場合、CSVヘッダーを書き込み
        """
        # ディレクトリが存在しない場合は作成
        dir_path = os.path.dirname(self.file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # ファイルが存在しない場合のみヘッダーを追加
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self._get_csv_columns())

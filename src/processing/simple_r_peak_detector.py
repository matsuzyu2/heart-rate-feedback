# 1次微分のゼロクロスと2次微分の閾値を使用してR波を検出
from typing import List, Optional, Callable
import numpy as np
import logging
from dataclasses import dataclass
from collections import deque

# ECG設定をインポート
from ..config.ecg_config import ECG_SAMPLING_RATE

# ログ設定
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BeatEvent:
    """
    検出されたR波イベントの情報
    
    Attributes:
        timestamp_ns (int): R波検出時刻（ナノ秒単位、絶対時刻）
        sample_index (int): サンプルインデックス
        amplitude (float): R波の振幅値
        rr_interval_ms (Optional[float]): 前回のR波からの間隔（ミリ秒単位）
    """
    timestamp_ns: int  # R波検出時刻（ナノ秒、絶対時刻）
    sample_index: int  # サンプルインデックス
    amplitude: float   # R波の振幅値
    rr_interval_ms: Optional[float] = None  # 前回のR波からの間隔（ミリ秒）


class SimpleRPeakDetector:
    """
    2次微分方式を使用したR波検出クラス
    
    アルゴリズム:
    1. 1次微分を計算（後退差分）
    2. 2次微分を計算（2階差分）
    3. 1次微分のゼロクロス（正→負）を検出
    4. 2次微分が負の閾値を下回ることを確認
    5. 閾値 = std(2次微分) × 3.5
    6. リフラクトリ期間で偽陽性を除去
    """
    
    def __init__(self, sampling_rate: Optional[int] = None):
        """
        R波検出器を初期化
        
        Args:
            sampling_rate (Optional[int]): サンプリング周波数（Hz）
        """
        self.sampling_rate = sampling_rate or ECG_SAMPLING_RATE
        
        # アルゴリズムパラメータ
        self.derivative_window_seconds = 5.0  # 微分統計窓サイズ（秒）
        self.derivative_threshold_coefficient = 2.5  # 2次微分閾値係数（感度向上のため3.5→2.5に緩和）
        self.refractory_period_ms = 180  # リフラクトリ期間（ミリ秒、頻脈対応のため200→180に短縮）
        
        # サンプル数に変換
        self.derivative_window_samples = int(self.derivative_window_seconds * self.sampling_rate)
        self.refractory_period_samples = int(self.refractory_period_ms * self.sampling_rate / 1000)
        
        # 信号バッファ
        self.signal_buffer = deque(maxlen=10)  # 微分計算用（少数でOK）
        self.timestamp_buffer = deque(maxlen=10)
        
        # 微分バッファ
        self.first_derivative_buffer = deque(maxlen=10)  # ゼロクロス検出用
        self.second_derivative_buffer = deque(maxlen=self.derivative_window_samples)  # 閾値計算用
        
        # 状態変数
        self.sample_count = 0
        self.last_peak_sample = -self.refractory_period_samples
        self.detected_peaks: List[BeatEvent] = []
        
        # 2次微分の動的閾値
        self.second_derivative_threshold = 0.0
        
        # コールバック関数
        self.beat_callback: Optional[Callable[[BeatEvent], None]] = None
    
    def set_beat_callback(self, callback: Callable[[BeatEvent], None]):
        """
        R波検出時のコールバック関数を設定
        
        Args:
            callback: R波検出時に呼び出される関数
        """
        self.beat_callback = callback
    
    def add_samples(self, samples: List[float], timestamps: List[int]) -> List[BeatEvent]:
        """
        新しいECGサンプルを追加し、R波を検出
        
        Args:
            samples: ECGサンプル値のリスト
            timestamps: 各サンプルのタイムスタンプ（ナノ秒）
            
        Returns:
            List[BeatEvent]: 検出されたR波イベントのリスト
        """
        if len(samples) != len(timestamps):
            raise ValueError("サンプル数とタイムスタンプ数が一致しません")
        
        detected_beats = []
        
        for sample, timestamp in zip(samples, timestamps):
            # 信号バッファに追加
            self.signal_buffer.append(sample)
            self.timestamp_buffer.append(timestamp)
            self.sample_count += 1
            
            # 微分を計算
            self._calculate_derivatives(sample)
            
            # 2次微分の閾値を更新
            self._update_derivative_threshold()
            
            # R波検出をチェック
            beat_event = self._check_r_peak_detection(sample, timestamp)
            if beat_event:
                detected_beats.append(beat_event)
                self.detected_peaks.append(beat_event)
                
                # コールバック呼び出し
                if self.beat_callback:
                    self.beat_callback(beat_event)
        
        return detected_beats
    
    def _calculate_derivatives(self, current_sample: float):
        """
        1次微分と2次微分を計算（因果的フィルタ）
        
        Args:
            current_sample: 現在のサンプル値
        """
        # 1次微分を計算（後退差分）
        if len(self.signal_buffer) >= 2:
            first_deriv = current_sample - self.signal_buffer[-2]
            self.first_derivative_buffer.append(first_deriv)
        
        # 2次微分を計算（2階差分）
        if len(self.signal_buffer) >= 3:
            second_deriv = current_sample - 2 * self.signal_buffer[-2] + self.signal_buffer[-3]
            self.second_derivative_buffer.append(second_deriv)
    
    def _update_derivative_threshold(self):
        """
        2次微分の動的閾値を更新
        """
        # 最低1秒分のデータが必要
        min_samples = min(self.derivative_window_samples, self.sampling_rate)
        if len(self.second_derivative_buffer) < min_samples:
            return
        
        # 2次微分の標準偏差を計算
        second_deriv_array = np.array(self.second_derivative_buffer)
        std_second_deriv = np.std(second_deriv_array)
        
        # 負の閾値を計算（Rスクリプト: sg2[i] < -th）
        self.second_derivative_threshold = -std_second_deriv * self.derivative_threshold_coefficient
    
    def _check_r_peak_detection(self, sample: float, timestamp: int) -> Optional[BeatEvent]:
        """
        現在のサンプルがR波かどうかを判定（2次微分方式）
        
        Args:
            sample: 現在のECGサンプル値
            timestamp: 現在のタイムスタンプ
            
        Returns:
            Optional[BeatEvent]: 検出されたR波イベント（検出されなかった場合はNone）
        """
        # 閾値が設定されていない場合はスキップ
        if self.second_derivative_threshold == 0.0:
            return None
        
        # リフラクトリ期間チェック
        if self.sample_count - self.last_peak_sample < self.refractory_period_samples:
            return None
        
        # 微分バッファが十分でない場合はスキップ
        if len(self.first_derivative_buffer) < 2 or len(self.second_derivative_buffer) < 1:
            return None
        
        # 条件1: 1次微分のゼロクロス（正→負）
        first_deriv_prev = self.first_derivative_buffer[-2]
        first_deriv_current = self.first_derivative_buffer[-1]
        
        is_zero_crossing = (first_deriv_prev > 0) and (first_deriv_current < 0)
        
        if not is_zero_crossing:
            return None
        
        # 条件2: 2次微分が負の閾値を下回る（急峻な下降）
        second_deriv_current = self.second_derivative_buffer[-1]
        
        is_sharp_peak = second_deriv_current < self.second_derivative_threshold
        
        if not is_sharp_peak:
            return None
        
        # 両方の条件を満たす場合、R波として検出
        beat_event = self._create_beat_event(sample, timestamp)
        self.last_peak_sample = self.sample_count
        
        logger.debug(f"R波検出: sample={sample:.2f}, "
                    f"1st_deriv_prev={first_deriv_prev:.2f}, 1st_deriv_curr={first_deriv_current:.2f}, "
                    f"2nd_deriv={second_deriv_current:.2f}, threshold={self.second_derivative_threshold:.2f}")
        
        return beat_event
    
    def _create_beat_event(self, amplitude: float, timestamp: int) -> BeatEvent:
        """
        BeatEventオブジェクトを作成
        
        Args:
            amplitude: R波の振幅
            timestamp: タイムスタンプ
            
        Returns:
            BeatEvent: 作成されたビートイベント
        """
        # RR間隔の計算
        rr_interval_ms = None
        if len(self.detected_peaks) > 0:
            last_beat = self.detected_peaks[-1]
            rr_interval_ns = timestamp - last_beat.timestamp_ns
            rr_interval_ms = rr_interval_ns / 1_000_000  # ナノ秒からミリ秒に変換
        
        return BeatEvent(
            timestamp_ns=timestamp,
            sample_index=self.sample_count,
            amplitude=amplitude,
            rr_interval_ms=rr_interval_ms
        )
    
    def reset(self):
        """検出器の状態をリセット"""
        self.signal_buffer.clear()
        self.timestamp_buffer.clear()
        self.first_derivative_buffer.clear()
        self.second_derivative_buffer.clear()
        self.sample_count = 0
        self.last_peak_sample = -self.refractory_period_samples
        self.detected_peaks.clear()
        self.second_derivative_threshold = 0.0


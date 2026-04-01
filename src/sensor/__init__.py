"""Sensor package."""
"""
センサー関連モジュール

このパッケージには以下のモジュールが含まれます:
- ecg_interface: Polar H10 ECGセンサーとのBLE通信
- cognio_trigger: Cognioトリガーシステムとの通信
- lsl_outlet: Lab Streaming Layer (LSL) マーカー送信
"""

from .ecg_interface import ECGInterface
from .cognio_trigger import CognioTrigger
from .lsl_outlet import LSLOutlet

__all__ = [
    "ECGInterface",
    "CognioTrigger",
    "LSLOutlet",
]

"""
視覚フィードバック GUI モジュール

Tkinter ベースのリアルタイム心拍ゲージ + 金銭的報酬カウンター。

スレッドモデル:
  - このクラスのインスタンスはメインスレッドで生成・操作する。
  - enqueue_state() / enqueue_session_end() はどのスレッドからでも呼べる（Queue 使用）。
  - start() を呼ぶとメインスレッドが Tkinter の mainloop() に入る。
"""
import platform
import queue
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

# モジュールレベル sentinel
_SESSION_END_SENTINEL = object()


def _get_system_font() -> str:
    """OS に応じた日本語対応フォントを返す。"""
    system = platform.system()
    if system == "Darwin":
        return "Hiragino Sans"
    elif system == "Windows":
        return "Meiryo"
    else:
        return "TkDefaultFont"


class VisualFeedbackGUI:
    """
    視覚フィードバック GUI

    リアルタイム HR ゲージ + 金銭的報酬カウンター + 残り時間表示。
    """

    # 色定数
    COLOR_BG = "#FFFFFF"
    COLOR_PANEL = "#FFFFFF"
    COLOR_TEXT = "#111111"
    COLOR_ON_TARGET = "#8FBC8F"
    COLOR_OFF_TARGET = "#BDBDBD"
    COLOR_REWARD_ACTIVE = "#FFC107"
    COLOR_REWARD_INACTIVE = "#888888"
    COLOR_CRITERION_LINE = "#444444"
    COLOR_GAUGE_BG = "#F2F2F2"

    def __init__(
        self,
        session_duration_seconds: int,
        shutdown_callback: Callable[[], None],
    ):
        """
        GUI の初期化。メインスレッドで呼ぶこと。

        Args:
            session_duration_seconds: セッション残り時間カウント用の総秒数
            shutdown_callback: × ボタン押下時に呼ぶコールバック
        """
        self._session_duration_seconds = session_duration_seconds
        self.shutdown_callback = shutdown_callback
        self._queue: queue.Queue = queue.Queue()
        self._start_time: Optional[float] = None
        self._closing: bool = False  # × ボタン連打防止フラグ

        self._font_family = _get_system_font()

        # --- Tkinter ウィンドウ構築 ---
        self._root = tk.Tk()
        self._root.title("")
        self._root.configure(bg=self.COLOR_BG)
        self._root.geometry("900x560")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self._build_ui()

    def _build_ui(self) -> None:
        """UI コンポーネントを構築する。"""
        font = self._font_family

        # --- ヘッダー ---
        header_frame = tk.Frame(self._root, bg=self.COLOR_PANEL, pady=18)
        header_frame.pack(fill=tk.X)

        self._timer_label = tk.Label(
            header_frame,
            text="残り --:--",
            font=(font, 15, "bold"),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_PANEL,
        )
        self._timer_label.pack(side=tk.RIGHT, padx=28)

        # --- メインコンテンツ ---
        main_frame = tk.Frame(self._root, bg=self.COLOR_BG, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左側: HR ゲージ
        gauge_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        gauge_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=56)

        self._hr_label = tk.Label(
            gauge_frame,
            text="心拍数",
            font=(font, 15),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
        )
        self._hr_label.pack(anchor=tk.W)

        self._hr_value_label = tk.Label(
            gauge_frame,
            text="-- BPM",
            font=(font, 40, "bold"),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
        )
        self._hr_value_label.pack(anchor=tk.W, pady=(8, 20))

        # ゲージ Canvas
        self._gauge_canvas = tk.Canvas(
            gauge_frame,
            width=150,
            height=300,
            bg=self.COLOR_GAUGE_BG,
            highlightthickness=1,
            highlightbackground="#D0D0D0",
        )
        self._gauge_canvas.pack(anchor=tk.W, pady=8)

        self._criterion_label = tk.Label(
            gauge_frame,
            text="目標: -- BPM",
            font=(font, 12),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_BG,
        )
        self._criterion_label.pack(anchor=tk.W, pady=(10, 0))

        # 右側: 報酬カウンター
        reward_frame = tk.Frame(main_frame, bg=self.COLOR_BG)
        reward_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=56)

        self._reward_label = tk.Label(
            reward_frame,
            text="¥ 0.0",
            font=(font, 36, "bold"),
            fg=self.COLOR_REWARD_INACTIVE,
            bg=self.COLOR_BG,
        )
        self._reward_label.pack(pady=(48, 8))

        self._reward_status_label = tk.Label(
            reward_frame,
            text="",
            font=(font, 12),
            fg=self.COLOR_REWARD_INACTIVE,
            bg=self.COLOR_BG,
        )
        self._reward_status_label.pack()

        # --- 状態インジケーター ---
        self._status_label = tk.Label(
            self._root,
            text="ベースライン設定中…",
            font=(font, 26, "bold"),
            fg=self.COLOR_REWARD_INACTIVE,
            bg=self.COLOR_BG,
            pady=28,
        )
        self._status_label.pack()

    def enqueue_state(self, state: dict) -> None:
        """
        asyncio スレッドから安全に呼べる状態更新メソッド。

        state のキー: current_hr_bpm, criterion_hr_bpm,
                     accumulated_reward_yen, is_on_target
        値は全て immutable 型（float, bool）のみとすること。
        """
        self._queue.put_nowait(state)

    def enqueue_session_end(self, total_yen: float) -> None:
        """セッション終了を通知する sentinel を queue に入れる。"""
        self._queue.put_nowait((_SESSION_END_SENTINEL, total_yen))

    def start(self) -> None:
        """
        Tkinter mainloop() を開始する。メインスレッドで呼ぶこと。
        この呼び出しはセッション終了または × ボタン押下までブロックする。
        """
        self._start_time = time.time()
        self._poll_queue()  # after() ポーリング開始
        self._root.mainloop()

    def _poll_queue(self) -> None:
        """200ms ごとに queue を確認して描画を更新する。"""
        try:
            while True:
                item = self._queue.get_nowait()
                if isinstance(item, tuple) and item[0] is _SESSION_END_SENTINEL:
                    total_yen = item[1]
                    self._show_session_end_dialog(total_yen)
                    return  # after() の再スケジュールをせず終了
                else:
                    self._update_display(item)
        except queue.Empty:
            pass
        self._update_timer_display()
        self._root.after(200, self._poll_queue)

    def _update_display(self, state: dict) -> None:
        """GUI 表示を最新の状態で更新する。"""
        current_hr = state["current_hr_bpm"]
        criterion_hr = state["criterion_hr_bpm"]
        reward_yen = state["accumulated_reward_yen"]
        is_on_target = state["is_on_target"]

        # HR 数値表示
        self._hr_value_label.config(text=f"{current_hr:.1f} BPM")

        # 基準表示
        self._criterion_label.config(text=f"目標: {criterion_hr:.1f} BPM")

        # ゲージ描画
        self._draw_gauge(current_hr, criterion_hr, is_on_target)

        # 報酬カウンター
        reward_color = (
            self.COLOR_REWARD_ACTIVE if is_on_target else self.COLOR_REWARD_INACTIVE
        )
        self._reward_label.config(
            text=f"¥ {reward_yen:.1f}",
            fg=reward_color,
        )
        self._reward_status_label.config(
            text="",
            fg=reward_color,
        )

        # 状態インジケーター
        if is_on_target:
            self._status_label.config(
                text="目標達成中",
                fg=self.COLOR_ON_TARGET,
            )
        else:
            self._status_label.config(
                text="目標未達成",
                fg=self.COLOR_REWARD_INACTIVE,
            )

    def _draw_gauge(
        self, current_hr: float, criterion_hr: float, is_on_target: bool
    ) -> None:
        """HR ゲージを Canvas 上に描画する。"""
        canvas = self._gauge_canvas
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1:
            width = 120
        if height <= 1:
            height = 260

        # 全体スケールを固定 (基準HRを中心に +/- 20 BPM)
        # これにより目標ラインの位置が常に一定になり、ゲージだけが上下する
        hr_min = criterion_hr - 20.0
        hr_max = criterion_hr + 20.0
        hr_range = hr_max - hr_min
        if hr_range <= 0:
            hr_range = 1

        # 目標ラインを超えたかどうかで色を変える
        reached_target = current_hr >= criterion_hr
        bar_color = self.COLOR_ON_TARGET if reached_target else self.COLOR_OFF_TARGET
        
        # ゲージの高さ（下から上に伸びる）
        # 値の割合を計算 (0.0=下端, 1.0=上端)
        ratio = (current_hr - hr_min) / hr_range
        ratio = max(0.0, min(1.0, ratio))
        
        # 上端の y 座標 (キャンバスは上が 0、下が height)
        bar_top_y = height - (ratio * height)
        
        # 縦ゲージを描画 (左右に 20px の余白を設ける)
        canvas.create_rectangle(
            20, bar_top_y, width - 20, height, fill=bar_color, outline=""
        )

        # 目標ライン (スケールの中央)
        criterion_ratio = (criterion_hr - hr_min) / hr_range
        criterion_y = height - (criterion_ratio * height)
        
        canvas.create_line(
            0, criterion_y, width, criterion_y,
            fill=self.COLOR_CRITERION_LINE, width=3,
        )
    def _update_timer_display(self) -> None:
        """残り時間を更新する。"""
        if self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        remaining = max(0, self._session_duration_seconds - elapsed)
        minutes = int(remaining) // 60
        seconds = int(remaining) % 60
        self._timer_label.config(text=f"残り {minutes:02d}:{seconds:02d}")

    def _show_session_end_dialog(self, total_yen: float) -> None:
        """セッション終了ダイアログを表示して root を閉じる。"""
        messagebox.showinfo(
            "セッション終了",
            f"お疲れ様でした。\n今回の獲得報酬: ¥ {total_yen:.1f}",
        )
        self._root.destroy()

    def _on_window_close(self) -> None:
        """
        × ボタン押下時のハンドラ。
        shutdown_callback 経由で asyncio のセッションを停止させる。
        GUI は即座に閉じず、on_session_end() による SESSION_END_SENTINEL を待つ。
        """
        if self._closing:
            return  # 二重呼び出し防止
        self._closing = True
        self._root.title("終了中...")
        self.shutdown_callback()

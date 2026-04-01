"""
視覚フィードバック GUI テストスクリプト

Polar H10 なしで GUI の表示・更新をテストする。
python tests/test_visual_gui.py で単独実行。

確認すべき項目:
  1. ゲージが HR 増加に合わせてリアルタイムに伸びること
  2. HR が基準を超えたときにゲージ色が青→緑に変わること
  3. 目標ラインが正しい位置に表示されること
  4. 報酬カウンターが on_target 中に加算されること
  5. セッション終了ダイアログが表示されること
  6. ダイアログを閉じるとウィンドウが閉じること
"""
import sys
import time
import threading
import math
import random
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# __init__.py を経由せず直接モジュールからインポート
# （pygame 未インストール環境でも動作させるため）
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "visual_feedback_gui",
    str(project_root / "src" / "feedback" / "visual_feedback_gui.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
VisualFeedbackGUI = _mod.VisualFeedbackGUI


def _dummy_data_thread(gui: VisualFeedbackGUI) -> None:
    """
    ダミーデータ生成スレッド。

    動作仕様:
            - 0〜8 秒: HR を 66 BPM 前後から緩やかに上昇（小さな上下動あり）
            - 8〜22 秒: HR を 74 BPM 前後で大きめに上下
            - 22〜30 秒: HR を 71 BPM 前後でやや落ち着いた上下
      - criterion_hr は 70.0 BPM で固定
      - 70.0 BPM を超えたら is_on_target=True、報酬を加算
      - 30 秒後に enqueue_session_end() を呼んで終了ダイアログを表示
    """
    criterion_hr = 70.0
    reward_rate = 1.0  # 円/秒
    accumulated_reward = 0.0
    update_interval = 0.2
    random.seed(42)
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        # 30 秒で終了
        if elapsed >= 30.0:
            gui.enqueue_session_end(accumulated_reward)
            return

        # HR の計算（トレンド + 周期変動 + ノイズ）
        if elapsed < 8.0:
            trend = 66.0 + (elapsed / 8.0) * 5.0
            periodic = 1.8 * math.sin(2.0 * math.pi * elapsed / 1.8)
        elif elapsed < 22.0:
            trend = 73.5 + 0.6 * math.sin(2.0 * math.pi * elapsed / 6.0)
            periodic = (
                2.8 * math.sin(2.0 * math.pi * elapsed / 1.3)
                + 1.2 * math.sin(2.0 * math.pi * elapsed / 0.55)
            )
        else:
            trend = 71.0 - ((elapsed - 22.0) / 8.0) * 1.2
            periodic = (
                1.7 * math.sin(2.0 * math.pi * elapsed / 1.7)
                + 0.8 * math.sin(2.0 * math.pi * elapsed / 0.8)
            )

        noise = random.uniform(-0.8, 0.8)
        current_hr = trend + periodic + noise
        current_hr = max(58.0, min(92.0, current_hr))

        # 達成判定
        is_on_target = current_hr >= criterion_hr

        # 報酬加算（更新間隔分）
        if is_on_target:
            accumulated_reward += reward_rate * update_interval

        # GUI に状態を送信
        gui.enqueue_state({
            "current_hr_bpm": current_hr,
            "criterion_hr_bpm": criterion_hr,
            "accumulated_reward_yen": accumulated_reward,
            "is_on_target": is_on_target,
        })

        time.sleep(update_interval)


def main() -> None:
    """テストのメイン関数。"""
    print("=" * 50)
    print("視覚フィードバック GUI テスト")
    print("=" * 50)
    print()
    print("テスト仕様:")
    print("  - 0〜8秒: HR が 66→71 BPM に緩やかに上昇（小さな変動あり）")
    print("  - 8〜22秒: HR が 74 BPM 前後で大きく上下")
    print("  - 22〜30秒: HR が 71 BPM 前後でやや落ち着いた上下")
    print("  - 目標: 70.0 BPM")
    print("  - 70 BPM 以上で 目標達成中（色変化）、報酬加算")
    print("  - 30秒後にセッション終了ダイアログ表示")
    print()
    print("確認ポイント:")
    print("  1. ゲージが HR 増加に追従すること")
    print("  2. 70 BPM 超過でゲージが青→緑に変化")
    print("  3. 目標ラインが正しい位置に表示")
    print("  4. 報酬カウンターが加算されること")
    print("  5. 終了ダイアログが表示されること")
    print("  6. ダイアログ閉じるとウィンドウも閉じる")
    print()

    def shutdown_callback() -> None:
        """× ボタンのテスト用コールバック。"""
        print("[テスト] × ボタンが押されました")

    gui = VisualFeedbackGUI(
        session_duration_seconds=30,
        shutdown_callback=shutdown_callback,
    )

    # ダミーデータ生成スレッドを起動
    t = threading.Thread(target=_dummy_data_thread, args=(gui,), daemon=True)
    t.start()

    # メインスレッドで GUI 起動
    gui.start()

    print("[テスト] GUI が正常に終了しました")


if __name__ == "__main__":
    main()

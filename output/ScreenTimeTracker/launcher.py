"""
屏幕使用时间 - 打包版启动入口
合并 tracker 后台采集 + desktop_ui 桌面界面，适配 PyInstaller 单文件打包
"""

import sys
import threading
from pathlib import Path

# PyInstaller 打包后 __file__ 路径会变，使用 sys._MEIPASS
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))


def run_tracker():
    """后台线程运行数据采集器"""
    try:
        from tracker import main as tracker_main
        tracker_main()
    except Exception as e:
        print(f"[Tracker] 采集器异常: {e}")


def main():
    # 启动后台采集器（守护线程）
    tracker_thread = threading.Thread(target=run_tracker, daemon=True)
    tracker_thread.start()

    # 启动桌面 UI（主线程，Qt 要求）
    from desktop_ui import launch
    launch()


if __name__ == "__main__":
    main()
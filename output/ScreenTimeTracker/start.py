"""
屏幕使用时间 - 启动脚本（桌面客户端版）
- start_ui: 启动桌面客户端 UI
- start_tracker: 仅启动后台采集器
- start_both: 启动采集器 + 桌面 UI
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
TRACKER_SCRIPT = PROJECT_DIR / "tracker.py"
UI_SCRIPT = PROJECT_DIR / "desktop_ui.py"
SOCKET_PORT = 19998


def is_tracker_running():
    """检查 tracker 是否在运行"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', SOCKET_PORT))
        s.close()
        return result == 0
    except Exception:
        return False


def start_tracker():
    """后台启动追踪器"""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # 回退

    subprocess.Popen(
        [pythonw, str(TRACKER_SCRIPT)],
        cwd=str(PROJECT_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    print("追踪器已启动（后台）")


def start_ui():
    """启动桌面客户端"""
    subprocess.Popen(
        [sys.executable, str(UI_SCRIPT)],
        cwd=str(PROJECT_DIR)
    )
    print("桌面客户端已启动")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="仅启动桌面 UI（采集已在后台时使用）")
    parser.add_argument("--tracker", action="store_true", help="仅启动后台采集器")
    args = parser.parse_args()

    if args.tracker:
        # 仅采集器模式
        if not is_tracker_running():
            start_tracker()
        else:
            print("追踪器已在运行中")
    elif args.ui:
        # 仅 UI 模式
        start_ui()
    else:
        # 完整模式：启动采集器 + UI
        if not is_tracker_running():
            start_tracker()
        else:
            print("追踪器已在运行中")
        time.sleep(0.5)
        start_ui()


if __name__ == "__main__":
    main()
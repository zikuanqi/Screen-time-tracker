"""
屏幕使用时间 - 启动脚本
- start_both: 启动采集器 + 面板，打开浏览器
- start_panel: 仅打开面板（采集已在后台运行）
"""

import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
TRACKER_SCRIPT = PROJECT_DIR / "tracker.py"
SERVER_SCRIPT = PROJECT_DIR / "server.py"
SOCKET_PORT = 19998
PANEL_URL = "http://127.0.0.1:19999"


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


def is_server_running():
    """检查面板服务器是否在运行"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', 19999))
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


def start_panel():
    """启动 Web 面板并打开浏览器"""
    if not is_server_running():
        subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            cwd=str(PROJECT_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        time.sleep(1.5)
    webbrowser.open(PANEL_URL)
    print(f"面板已打开: {PANEL_URL}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", action="store_true", help="仅打开面板（采集已在后台时使用）")
    args = parser.parse_args()

    if args.panel:
        # 仅面板模式：「屏幕使用时间面板」
        if not is_server_running():
            subprocess.Popen(
                [sys.executable, str(SERVER_SCRIPT)],
                cwd=str(PROJECT_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            time.sleep(1.5)
        webbrowser.open(PANEL_URL)
        print("面板已打开")
    else:
        # 完整模式：「屏幕使用时间」
        if not is_tracker_running():
            start_tracker()
        else:
            print("追踪器已在运行中")
        start_panel()


if __name__ == "__main__":
    main()
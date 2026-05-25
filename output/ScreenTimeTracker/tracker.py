"""
屏幕使用时间追踪 - 后台采集模块
记录真实使用情况：活动检测、进程前台/后台统计、Windows通知
"""

import os
import sys
import time
import json
import sqlite3
import threading
import struct
import socket
from datetime import datetime, date, timedelta
from pathlib import Path

import ctypes
import psutil
try:
    import win32gui
    import win32process
    import win32api
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "screen_time.db"
NOTIFY_DB_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"

INTERVAL = 5  # 采集间隔（秒）
IDLE_THRESHOLD = 300  # 空闲阈值（秒），超过5分钟算离开
SOCKET_PORT = 19998  # 用于检查 tracker 是否已在运行


def get_idle_seconds():
    """获取用户空闲秒数（GetLastInputInfo），返回 -1 表示不可用"""
    if not WIN32_AVAILABLE:
        return -1
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ok = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        if ok:
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0, millis / 1000.0)
        else:
            import traceback
            with open(str(PROJECT_DIR / "tracker_error.log"), "a") as f:
                f.write(f"[{datetime.now()}] GetLastInputInfo returned False, GetLastError={ctypes.windll.kernel32.GetLastError()}\n")
            return 0  # fallback: 假设用户活跃
    except Exception as e:
        import traceback
        with open(str(PROJECT_DIR / "tracker_error.log"), "a") as f:
            f.write(f"[{datetime.now()}] Exception in get_idle_seconds: {e}\n{traceback.format_exc()}\n")
        return 0  # fallback: 假设用户活跃


def get_foreground_process_name():
    """获取前台窗口的进程名"""
    if not WIN32_AVAILABLE:
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        name = proc.name()
        return name
    except Exception:
        return None


def get_process_icon(proc_name):
    """提取进程图标为 base64"""
    try:
        for proc in psutil.process_iter(['name', 'exe']):
            if proc.info['name'] and proc.info['name'].lower() == proc_name.lower():
                exe_path = proc.info['exe']
                if exe_path and os.path.exists(exe_path):
                    import base64
                    from PIL import Image
                    import win32ui
                    import win32gui
                    import win32con
                    import win32api
                    # 获取图标
                    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                    ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
                    large, small = win32gui.ExtractIconEx(exe_path, 0)
                    if large:
                        hicon = large[0]
                    elif small:
                        hicon = small[0]
                    else:
                        return None
                    try:
                        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                        hbmp = win32ui.CreateBitmap()
                        hbmp.CreateCompatibleBitmap(hdc, 32, 32)
                        memdc = hdc.CreateCompatibleDC()
                        memdc.SelectObject(hbmp)
                        memdc.DrawIcon((0, 0), hicon)
                        bmpinfo = hbmp.GetInfo()
                        bmpstr = hbmp.GetBitmapBits(True)
                        img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                               bmpstr, 'raw', 'BGRA', 0, 1)
                        img = img.resize((32, 32), Image.LANCZOS)
                        import io
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        return base64.b64encode(buf.getvalue()).decode()
                    finally:
                        for h in large:
                            win32gui.DestroyIcon(h)
                        for h in small:
                            win32gui.DestroyIcon(h)
                        win32gui.DeleteObject(hbmp.GetHandle())
                        memdc.DeleteDC()
                        hdc.DeleteDC()
                    return None
    except Exception:
        pass
    return None


def read_notification_counts():
    """从Windows通知数据库读取今天的通知计数"""
    counts = {}
    if not NOTIFY_DB_PATH.exists():
        return counts
    try:
        conn = sqlite3.connect(str(NOTIFY_DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        today_start = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
        cur.execute("""
            SELECT AppId, COUNT(*) as cnt
            FROM Notification
            WHERE ArrivalTime >= ?
            GROUP BY AppId
        """, (today_start,))
        for row in cur.fetchall():
            app_id = row['AppId'] or "Unknown"
            counts[app_id] = row['cnt']
        conn.close()
    except Exception:
        pass
    return counts


def get_notification_count_today():
    """返回今天总通知数和各来源"""
    counts = read_notification_counts()
    total = sum(counts.values())
    return total, counts


def get_db():
    """获取数据库连接并初始化表结构"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_active_seconds REAL,
            total_idle_seconds REAL,
            notification_count INTEGER,
            notification_sources TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS process_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            process_name TEXT,
            foreground_seconds REAL,
            background_seconds REAL,
            open_count INTEGER,
            notification_count INTEGER,
            last_updated TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            process_name TEXT,
            is_foreground INTEGER
        )
    """)
    conn.commit()
    return conn


def update_daily_summary(conn, date_str, active_delta=0, idle_delta=0):
    """更新每日摘要"""
    cur = conn.cursor()
    cur.execute("SELECT total_active_seconds, total_idle_seconds FROM daily_summary WHERE date=?", (date_str,))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE daily_summary
            SET total_active_seconds = total_active_seconds + ?,
                total_idle_seconds = total_idle_seconds + ?
            WHERE date = ?
        """, (active_delta, idle_delta, date_str))
    else:
        cur.execute("""
            INSERT INTO daily_summary (date, total_active_seconds, total_idle_seconds, notification_count, notification_sources)
            VALUES (?, ?, ?, 0, '{}')
        """, (date_str, active_delta, idle_delta))
    conn.commit()


def update_process_usage(conn, date_str, process_name, is_foreground, open_count=0):
    """更新进程使用统计"""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, foreground_seconds, background_seconds, open_count
        FROM process_usage
        WHERE date=? AND process_name=?
    """, (date_str, process_name))
    row = cur.fetchone()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if row:
        fg = row[1] + (INTERVAL if is_foreground else 0)
        bg = row[2] + (0 if is_foreground else INTERVAL)
        oc = row[3] + open_count
        cur.execute("""
            UPDATE process_usage
            SET foreground_seconds=?, background_seconds=?, open_count=?, last_updated=?
            WHERE id=?
        """, (fg, bg, oc, now_str, row[0]))
    else:
        fg = INTERVAL if is_foreground else 0
        bg = 0 if is_foreground else INTERVAL
        cur.execute("""
            INSERT INTO process_usage (date, process_name, foreground_seconds, background_seconds, open_count, notification_count, last_updated)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (date_str, process_name, fg, bg, open_count, now_str))
    conn.commit()


def update_notification_data(conn, date_str):
    """更新通知数据到数据库"""
    total, sources = get_notification_count_today()
    cur = conn.cursor()
    cur.execute("""
        UPDATE daily_summary
        SET notification_count=?, notification_sources=?
        WHERE date=?
    """, (total, json.dumps(sources, ensure_ascii=False), date_str))
    # 尝试把通知来源映射到进程
    for app_id, cnt in sources.items():
        proc_name = app_id.split(".")[-1] if "." in app_id else app_id
        cur.execute("SELECT id, notification_count FROM process_usage WHERE date=? AND process_name=?", (date_str, proc_name))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE process_usage SET notification_count=? WHERE id=?", (cnt, row[0]))
        else:
            cur.execute("""
                INSERT INTO process_usage (date, process_name, foreground_seconds, background_seconds, open_count, notification_count, last_updated)
                VALUES (?, ?, 0, 0, 0, ?, ?)
            """, (date_str, proc_name, cnt, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()


def is_already_running():
    """检查是否已有 tracker 实例在运行"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', SOCKET_PORT))
        s.close()
        return result == 0
    except Exception:
        return False


def start_socket_listener():
    """启动 socket 监听，让其他进程可以检查 tracker 状态"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', SOCKET_PORT))
        s.listen(1)
        def listen_loop():
            while True:
                try:
                    conn, _ = s.accept()
                    conn.send(b"ok")
                    conn.close()
                except Exception:
                    break
        t = threading.Thread(target=listen_loop, daemon=True)
        t.start()
    except Exception:
        pass


def main():
    if is_already_running():
        print("Tracker 已在运行中")
        return

    start_socket_listener()

    conn = get_db()
    today = date.today().isoformat()
    known_processes = set()
    prev_foreground = None
    last_notif_update = 0

    print(f"屏幕使用时间追踪已启动，每 {INTERVAL}s 采集一次")
    print(f"数据库: {DB_PATH}")

    try:
        while True:
            now = time.time()
            idle_sec = get_idle_seconds()
            is_active = idle_sec >= 0 and idle_sec < IDLE_THRESHOLD

            date_str = date.today().isoformat()
            if date_str != today:
                # 跨日
                update_notification_data(conn, today)
                today = date_str

            if is_active:
                update_daily_summary(conn, date_str, active_delta=INTERVAL, idle_delta=0)

                # 获取前台进程
                fg_name = get_foreground_process_name()
                if fg_name and fg_name not in known_processes:
                    known_processes.add(fg_name)

                # 统计前台进程使用
                if fg_name:
                    update_process_usage(conn, date_str, fg_name, is_foreground=True,
                                         open_count=1 if fg_name != prev_foreground else 0)

                # 获取所有正在运行的进程（后台统计）
                running_procs = set()
                try:
                    for proc in psutil.process_iter(['name']):
                        name = proc.info['name']
                        if name:
                            running_procs.add(name)
                except Exception:
                    pass

                for pname in running_procs:
                    is_fg = (pname == fg_name)
                    if not is_fg:
                        update_process_usage(conn, date_str, pname, is_foreground=False)

                prev_foreground = fg_name

                # 记录采样
                if fg_name:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO usage_samples (timestamp, process_name, is_foreground) VALUES (?, ?, 1)",
                                (datetime.now().strftime("%Y-%m-%d %H:%M"), fg_name))
                    conn.commit()

            else:
                update_daily_summary(conn, date_str, active_delta=0, idle_delta=INTERVAL)

            # 通知数据每分钟更新一次
            if now - last_notif_update > 60:
                update_notification_data(conn, date_str)
                last_notif_update = now

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("追踪已停止")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
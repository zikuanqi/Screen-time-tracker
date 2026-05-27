"""
屏幕使用时间 - 桌面客户端 (PySide6)
iOS 风格 UI，直接桌面显示，替代 Web 面板
"""

import os
import sys
import json
import sqlite3
import base64
import math
from datetime import datetime, date, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QGridLayout,
    QSystemTrayIcon, QMenu, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QFontDatabase,
    QPainterPath, QLinearGradient, QIcon, QAction, QPixmap,
    QScreen
)

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "screen_time.db"

# ─── 颜色常量 (iOS 风格) ────────────────────

BG = "#F2F2F7"
CARD_BG = "#FFFFFF"
ACCENT = "#5E5CE6"
ACCENT2 = "#30D158"
ACCENT3 = "#FF9F0A"
ACCENT4 = "#FF375F"
TEXT = "#1C1C1E"
TEXT2 = "#8E8E93"
SEP = "#E5E5EA"
RADIUS = 16


# ─── 数据库工具 ─────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def stats_for_date(target_date):
    conn = get_db()
    d = target_date.isoformat() if isinstance(target_date, date) else target_date
    summary = conn.execute("SELECT * FROM daily_summary WHERE date=?", (d,)).fetchone()
    processes = conn.execute(
        "SELECT * FROM process_usage WHERE date=? ORDER BY (foreground_seconds+background_seconds) DESC",
        (d,)
    ).fetchall()
    conn.close()
    total_active = summary['total_active_seconds'] if summary else 0
    total_idle = summary['total_idle_seconds'] if summary else 0
    result = {
        "date": d, "total_active_seconds": total_active, "total_idle_seconds": total_idle,
        "notification_count": summary['notification_count'] if summary else 0,
        "processes": []
    }
    for p in processes:
        result["processes"].append({
            "name": p["process_name"],
            "foreground_seconds": p["foreground_seconds"] or 0,
            "background_seconds": p["background_seconds"] or 0,
            "open_count": p["open_count"] or 0,
            "notification_count": p["notification_count"] or 0
        })
    return result


def range_data(start, end):
    conn = get_db()
    rows = conn.execute(
        "SELECT date, total_active_seconds, notification_count FROM daily_summary WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end)
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "total_active_seconds": r["total_active_seconds"],
             "notification_count": r["notification_count"]} for r in rows]


def days_with_data():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT date FROM daily_summary ORDER BY date").fetchall()
    conn.close()
    return [r["date"] for r in rows]


# ─── 格式化 ─────────────────────────────────

def fmt_time(s):
    s = round(s)
    if s < 60: return f"{s}秒"
    m = s // 60
    h = m // 60
    m = m % 60
    if h > 0: return f"{h}小时{m}分" if m > 0 else f"{h}小时"
    return f"{m}分钟"


def fmt_short(s):
    s = round(s)
    if s < 60: return f"{s}s"
    m = s // 60
    h = m // 60
    m = m % 60
    if h > 0: return f"{h}h{m}m" if m > 0 else f"{h}h"
    return f"{m}m"


# ─── 主窗口 ─────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("屏幕使用时间")
        self.setMinimumSize(560, 700)
        self.resize(800, 800)
        self.setStyleSheet(f"background-color: {BG};")

        # 居中
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - 800) // 2, (screen.height() - 800) // 2)

        # 设置窗口图标
        icon_path = str(PROJECT_DIR / "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 中央滚动
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"border: none; background: {BG};")
        self.setCentralWidget(self.scroll)

        self.content = QWidget()
        self.content.setStyleSheet(f"background: {BG};")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(20, 16, 20, 32)
        self.layout.setSpacing(0)

        # 标题
        self.build_header()
        # 摘要卡片
        self.build_summary()
        # 分段控件
        self.build_segmented()
        # 时间轴
        self.build_timeline()
        # 进程列表
        self.build_process_list()
        # 使用建议
        self.build_advice()

        self.layout.addStretch()
        self.scroll.setWidget(self.content)

        # 数据状态
        self.current_mode = "1d"
        self.all_dates = []

        # 自动刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)

        # 系统托盘
        self._allow_exit = False
        self.build_tray()

        self.refresh_data()

    # ─── 系统托盘 ──────────────────────────────

    def build_tray(self):
        """常驻系统托盘：关闭窗口最小化到托盘，右键菜单可显示/退出"""
        icon_path = str(PROJECT_DIR / "icon.ico")
        tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("屏幕使用时间")

        menu = QMenu()
        show_act = QAction("显示窗口", self)
        show_act.triggered.connect(self.show_from_tray)
        menu.addAction(show_act)

        hide_act = QAction("隐藏窗口", self)
        hide_act.triggered.connect(self.hide)
        menu.addAction(hide_act)

        menu.addSeparator()

        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self.quit_app)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        # 单击/双击托盘图标都切换显示
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self.show_from_tray()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._allow_exit = True
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """关闭按钮 → 最小化到托盘；只有从托盘菜单退出才真正关闭"""
        if self._allow_exit or not self.tray:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "屏幕使用时间",
            "已最小化到托盘，继续在后台运行。右键托盘图标可退出。",
            QSystemTrayIcon.Information,
            3000,
        )

    # ─── 标题 ──────────────────────────────

    def build_header(self):
        h = QLabel()
        h.setTextFormat(Qt.RichText)
        h.setText(f'<div style="text-align:center;font-size:34px;font-weight:700;letter-spacing:-0.5px;color:{TEXT}">'
                  f'<span style="color:{ACCENT}">屏幕</span>使用时间</div>')
        h.setStyleSheet(f"background: transparent; padding: 16px 0 4px;")
        self.layout.addWidget(h)

        self.date_sub = QLabel()
        self.date_sub.setAlignment(Qt.AlignCenter)
        self.date_sub.setStyleSheet(f"font-size:13px; color:{TEXT2}; padding-bottom:12px;")
        self.layout.addWidget(self.date_sub)

    # ─── 摘要卡片 ───────────────────────────

    def build_summary(self):
        self.summary_wrap = QWidget()
        grid = QGridLayout(self.summary_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        items = [
            ("vActive", "活跃时间", ACCENT),
            ("vOpens", "打开次数", ACCENT4),
            ("vNotifs", "通知数", ACCENT3),
        ]
        for i, (name, label, color) in enumerate(items):
            card = QFrame()
            card.setStyleSheet(self.card_style())
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 18, 20, 18)
            cl.setSpacing(4)

            val = QLabel("--")
            val.setObjectName(name)
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet(f"font-size:28px; font-weight:700; color:{color}; background:transparent;")
            cl.addWidget(val)

            lb = QLabel(label)
            lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet(f"font-size:11px; color:{TEXT2}; text-transform:uppercase; letter-spacing:0.5px; background:transparent;")
            cl.addWidget(lb)

            grid.addWidget(card, 0, i)

        self.summary_wrap.setStyleSheet("background: transparent;")
        self.layout.addWidget(self.summary_wrap)
        self.layout.addSpacing(20)

    # ─── 分段控件 ───────────────────────────

    def build_segmented(self):
        self.seg_wrap = QWidget()
        seg = QHBoxLayout(self.seg_wrap)
        seg.setContentsMargins(2, 2, 2, 2)
        seg.setSpacing(0)
        self.seg_wrap.setStyleSheet(f"background: #E5E5EA; border-radius: 9px;")

        modes = [("1d", "今天"), ("7d", "本周"), ("30d", "本月")]
        self.seg_btns = {}
        for key, label in modes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(self.seg_btn_style(False))
            btn.clicked.connect(lambda checked, k=key: self.switch_mode(k))
            seg.addWidget(btn)
            self.seg_btns[key] = btn

        self.seg_btns["1d"].setChecked(True)
        self.seg_btns["1d"].setStyleSheet(self.seg_btn_style(True))
        self.seg_wrap.setFixedHeight(40)
        self.layout.addWidget(self.seg_wrap)
        self.layout.addSpacing(16)

    # ─── 时间轴 ──────────────────────────────

    def build_timeline(self):
        self.tl_widget = TimelineWidget()
        self.tl_widget.setMinimumHeight(220)
        self.tl_widget.setMaximumHeight(220)
        self.layout.addWidget(self.tl_widget)
        self.layout.addSpacing(12)

    # ─── 进程列表 ────────────────────────────

    def build_process_list(self):
        self.proc_header = QFrame()
        self.proc_header.setStyleSheet(self.card_style_top())
        hl = QHBoxLayout(self.proc_header)
        hl.setContentsMargins(20, 14, 20, 8)
        n = QLabel("软件")
        n.setStyleSheet(f"font-size:13px; font-weight:600; color:{TEXT2}; background:transparent; text-transform:uppercase; letter-spacing:0.5px;")
        hl.addWidget(n, 1)
        t = QLabel("使用时长")
        t.setAlignment(Qt.AlignRight)
        t.setFixedWidth(80)
        t.setStyleSheet(f"font-size:13px; font-weight:600; color:{TEXT2}; background:transparent;")
        hl.addWidget(t)
        o = QLabel("打开次数")
        o.setAlignment(Qt.AlignRight)
        o.setFixedWidth(70)
        o.setStyleSheet(f"font-size:13px; font-weight:600; color:{TEXT2}; background:transparent;")
        hl.addWidget(o)
        self.layout.addWidget(self.proc_header)

        self.proc_container = QFrame()
        self.proc_container.setStyleSheet(self.card_style_bottom())
        self.proc_layout = QVBoxLayout(self.proc_container)
        self.proc_layout.setContentsMargins(0, 0, 0, 0)
        self.proc_layout.setSpacing(0)
        self.layout.addWidget(self.proc_container)
        self.layout.addSpacing(20)

    # ─── 使用建议 ────────────────────────────

    def build_advice(self):
        self.advice_card = QFrame()
        self.advice_card.setStyleSheet(self.card_style())
        av = QVBoxLayout(self.advice_card)
        av.setContentsMargins(20, 18, 20, 18)

        title = QLabel("使用建议")
        title.setStyleSheet(f"font-size:18px; font-weight:600; color:{TEXT}; background:transparent;")
        av.addWidget(title)
        av.addSpacing(8)

        self.advice_content = QLabel()
        self.advice_content.setWordWrap(True)
        self.advice_content.setStyleSheet(f"font-size:14px; color:{TEXT2}; background:transparent; line-height:1.8;")
        av.addWidget(self.advice_content)

        self.layout.addWidget(self.advice_card)

    # ─── 样式 ──────────────────────────────

    def card_style(self):
        return f"background:{CARD_BG}; border-radius:{RADIUS}px;"

    def card_style_top(self):
        return f"background:{CARD_BG}; border-top-left-radius:{RADIUS}px; border-top-right-radius:{RADIUS}px;"

    def card_style_bottom(self):
        return f"background:{CARD_BG}; border-bottom-left-radius:{RADIUS}px; border-bottom-right-radius:{RADIUS}px;"

    def seg_btn_style(self, active):
        if active:
            return (f"background: #fff; border: none; border-radius: 7px; "
                    f"color: {TEXT}; font-size: 14px; font-weight: 500; padding: 8px 0;")
        return (f"background: transparent; border: none; border-radius: 7px; "
                f"color: {TEXT}; font-size: 14px; font-weight: 400; padding: 8px 0;")

    # ─── 切换模式 ────────────────────────────

    def switch_mode(self, mode):
        self.current_mode = mode
        for k, btn in self.seg_btns.items():
            btn.setChecked(k == mode)
            btn.setStyleSheet(self.seg_btn_style(k == mode))
        self.refresh_data()

    # ─── 刷新数据 ────────────────────────────

    def refresh_data(self):
        self.all_dates = days_with_data()
        today_str = date.today().isoformat()

        if self.current_mode == "1d":
            s = stats_for_date(date.today())
            self.update_ui(s, "1d")

            now = datetime.now()
            self.date_sub.setText(now.strftime("%Y年%m月%d日 %A"))

            # 时间轴数据
            samples = self.get_samples_for_today()
            self.tl_widget.set_day_data(samples)

        elif self.current_mode in ("7d", "30d"):
            days = 7 if self.current_mode == "7d" else 30
            start = (date.today() - timedelta(days=days - 1)).isoformat()
            end = today_str
            rdata = range_data(start, end)
            self.tl_widget.set_range_data(rdata)

            total_active = sum(d["total_active_seconds"] for d in rdata)
            total_notif = sum(d["notification_count"] for d in rdata)
            # 汇总进程
            proc_map = {}
            for d in rdata:
                ds = stats_for_date(d["date"])
                for p in ds["processes"]:
                    key = p["name"]
                    if key not in proc_map:
                        proc_map[key] = {"name": key, "foreground_seconds": 0, "background_seconds": 0,
                                         "open_count": 0, "notification_count": 0}
                    proc_map[key]["foreground_seconds"] += p["foreground_seconds"]
                    proc_map[key]["background_seconds"] += p["background_seconds"]
                    proc_map[key]["open_count"] += p["open_count"]
                    proc_map[key]["notification_count"] += p["notification_count"]

            merged = {
                "date": f"{start} ~ {end}",
                "total_active_seconds": total_active,
                "total_idle_seconds": 0,
                "notification_count": total_notif,
                "processes": sorted(proc_map.values(),
                                    key=lambda x: x["foreground_seconds"] + x["background_seconds"],
                                    reverse=True)
            }
            label = "最近 7 天汇总" if self.current_mode == "7d" else "最近 30 天汇总"
            self.date_sub.setText(label)
            self.update_ui(merged, self.current_mode)

    def get_samples_for_today(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT timestamp, process_name, is_foreground FROM usage_samples WHERE date(timestamp)=? ORDER BY timestamp",
            (date.today().isoformat(),)
        ).fetchall()
        conn.close()
        return [{"timestamp": r["timestamp"], "process_name": r["process_name"], "is_foreground": r["is_foreground"]}
                for r in rows]

    # ─── 更新 UI ────────────────────────────

    def update_ui(self, data, mode):
        total = data.get("total_active_seconds", 0)
        processes = data.get("processes", [])

        self.findChild(QLabel, "vActive").setText(fmt_time(total))
        total_opens = sum(p.get("open_count", 0) for p in processes)
        self.findChild(QLabel, "vOpens").setText(str(total_opens))
        self.findChild(QLabel, "vNotifs").setText(str(data.get("notification_count", 0)))

        # 进程列表
        self.update_processes(processes, total)

        # 建议
        if len(self.all_dates) >= 3:
            self.update_advice(data)
        elif len(self.all_dates) > 0:
            self.advice_content.setText("数据不足3天，再用几天才能给出个性化建议。")
            self.advice_card.show()
        else:
            self.advice_card.hide()

    def update_processes(self, processes, total):
        # 清空旧 widget
        while self.proc_layout.count():
            item = self.proc_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        max_fg = max((p.get("foreground_seconds", 0) for p in processes), default=0)

        count = 0
        for p in processes:
            total_sec = p.get("foreground_seconds", 0) + p.get("background_seconds", 0)
            if total_sec < 5:
                continue
            count += 1
            bar_w = (p.get("foreground_seconds", 0) / max_fg * 100) if max_fg > 0 else 0
            fg = p.get("foreground_seconds", 0)
            bg = p.get("background_seconds", 0)
            nf = p.get("notification_count", 0)
            oc = p.get("open_count", 0)

            row = QFrame()
            row.setStyleSheet(f"background: {CARD_BG}; border-top: 1px solid {SEP};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(20, 10, 20, 10)
            rl.setSpacing(12)

            # 图标占位
            icon_lbl = QLabel(p["name"][0].upper())
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setFixedSize(32, 32)
            icon_lbl.setStyleSheet(f"background:#E8E8ED; border-radius:8px; font-size:15px; font-weight:600; color:{TEXT2}; border:none;")
            rl.addWidget(icon_lbl)

            # 名称 + 标签 + 进度条
            info = QVBoxLayout()
            info.setSpacing(3)
            name_lbl = QLabel(p["name"])
            name_lbl.setStyleSheet(f"font-size:15px; font-weight:500; color:{TEXT}; background:transparent; border:none;")
            info.addWidget(name_lbl)

            tags = QHBoxLayout()
            tags.setSpacing(6)
            fg_tag = QLabel(f"前台 {fmt_short(fg)}")
            fg_tag.setStyleSheet(f"font-size:11px; color:#1C7D30; background:#D4F5DD; border-radius:4px; padding:2px 6px;")
            tags.addWidget(fg_tag)
            bg_tag = QLabel(f"后台 {fmt_short(bg)}")
            bg_tag.setStyleSheet(f"font-size:11px; color:#636366; background:#E8E8ED; border-radius:4px; padding:2px 6px;")
            tags.addWidget(bg_tag)
            if nf > 0:
                nf_tag = QLabel(f"通知 {nf}")
                nf_tag.setStyleSheet(f"font-size:11px; color:{TEXT2}; background:#F0F0F5; border-radius:4px; padding:2px 6px;")
                tags.addWidget(nf_tag)
            tags.addStretch()
            info.addLayout(tags)

            # 进度条
            bar = QFrame()
            bar.setFixedHeight(3)
            bar.setStyleSheet(f"background:#E5E5EA; border-radius:2px; border:none;")
            fill = QFrame(bar)
            fill.setFixedHeight(3)
            fill.setFixedWidth(int(bar_w / 100 * 300))
            fill.setStyleSheet(f"background:{ACCENT}; border-radius:2px; border:none;")
            info.addWidget(bar)

            rl.addLayout(info, 1)

            # 时长
            time_lbl = QLabel(fmt_short(total_sec))
            time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            time_lbl.setFixedWidth(80)
            time_lbl.setStyleSheet(f"font-size:15px; font-weight:600; color:{TEXT}; background:transparent;")
            rl.addWidget(time_lbl)

            # 打开次数
            oc_lbl = QLabel(f"{oc}次")
            oc_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            oc_lbl.setFixedWidth(70)
            oc_lbl.setStyleSheet(f"font-size:14px; color:{TEXT2}; background:transparent;")
            rl.addWidget(oc_lbl)

            self.proc_layout.addWidget(row)

    def update_advice(self, data):
        tips = []
        total_sec = data.get("total_active_seconds", 0)
        processes = data.get("processes", [])

        # 晚上10点后娱乐软件
        now = datetime.now()
        if now.hour >= 22:
            ent_key = ["chrome", "msedge", "steam", "firefox", "bilibili", "qq", "wechat", "edge"]
            ent_time = 0
            for p in processes:
                n = p["name"].lower()
                if any(k in n for k in ent_key):
                    ent_time += p.get("foreground_seconds", 0)
            if ent_time > 1800:
                tips.append("晚上10点后娱乐软件使用超过30分钟，建议早点休息。")

        # 单软件异常
        for p in processes[:3]:
            fg = p.get("foreground_seconds", 0)
            if fg > 7200 and ".exe" in p.get("name", "").lower():
                tips.append(f"「{p['name']}」今天前台使用超过2小时，适当休息一下。")

        if not tips:
            tips.append("今天的使用习惯良好 👍")

        lines = "\n".join(f"• {t}" for t in tips)
        self.advice_content.setText(lines)
        self.advice_card.show()


# ─── 时间轴控件 ─────────────────────────────

class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.day_data = []
        self.range_data = []
        self.mode = "1d"
        self.setStyleSheet(f"background: {CARD_BG}; border-radius: {RADIUS}px;")

    def set_day_data(self, samples):
        self.day_data = samples
        self.mode = "1d"
        self.update()

    def set_range_data(self, data):
        self.range_data = data
        self.mode = "range"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        margin_l, margin_r, margin_t, margin_b = 44, 20, 20, 32

        # 网格线
        pen = QPen(QColor(SEP), 0.5)
        painter.setPen(pen)
        chart_h = h - margin_t - margin_b
        chart_y = margin_t
        for i in range(1, 4):
            y = chart_y + i * chart_h / 4
            painter.drawLine(QPointF(margin_l, y), QPointF(w - margin_r, y))

        # Y 轴标签
        for i in range(2):
            painter.setPen(QColor(TEXT2))
            f = painter.font(); f.setPixelSize(11); painter.setFont(f)
            y = chart_y + (i + 1) * chart_h / 2
            painter.drawText(QRectF(2, y - 8, margin_l - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{i}h")

        chart_w = w - margin_l - margin_r

        if self.mode == "1d" and self.day_data:
            self._draw_day(painter, margin_l, chart_y, chart_w, chart_h)
        elif self.mode == "range" and self.range_data:
            self._draw_range(painter, margin_l, chart_y, chart_w, chart_h)
        else:
            painter.setPen(QColor(TEXT2))
            f = painter.font(); f.setPixelSize(13); painter.setFont(f)
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "暂无数据")
            return

        painter.end()

    def _draw_day(self, painter, x0, y0, w, h):
        hours = [0] * 24
        for s in self.day_data:
            idx = int(s["timestamp"][11:13])
            if 0 <= idx < 24:
                hours[idx] += 5
        max_v = max(3600, max(hours))
        bar_w = max(2, w / 24 - 2)

        for i in range(24):
            bh = (hours[i] / max_v * h * 0.65) if hours[i] > 0 else 0
            bx = x0 + i * (w / 24) + 1
            grad = QLinearGradient(bx, y0 + h - bh, bx, y0 + h)
            grad.setColorAt(0, QColor(ACCENT))
            grad.setColorAt(1, QColor(94, 92, 230, 64))
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, y0 + h - bh, bar_w, bh), 2, 2)
            painter.fillPath(path, grad)

        for i in range(0, 24, 3):
            painter.setPen(QColor(TEXT2))
            f = painter.font(); f.setPixelSize(10); painter.setFont(f)
            cx = x0 + i * (w / 24) + w / 48
            painter.drawText(QRectF(cx - 14, y0 + h + 6, 28, 14), Qt.AlignCenter, f"{i}:00")

    def _draw_range(self, painter, x0, y0, w, h):
        data = self.range_data
        max_v = max(3600, max(d["total_active_seconds"] for d in data))
        bar_w = max(3, w / len(data) - 2)

        for i, d in enumerate(data):
            val = d["total_active_seconds"]
            bh = max(2, (val / max_v * h * 0.65))
            bx = x0 + i * (w / len(data)) + 1
            grad = QLinearGradient(bx, y0 + h - bh, bx, y0 + h)
            grad.setColorAt(0, QColor(ACCENT))
            grad.setColorAt(1, QColor(94, 92, 230, 64))
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, y0 + h - bh, bar_w, bh), 2, 2)
            painter.fillPath(path, grad)

        step = max(1, len(data) // 10) if len(data) > 10 else 1
        for i in range(0, len(data), step):
            painter.setPen(QColor(TEXT2))
            f = painter.font(); f.setPixelSize(10); painter.setFont(f)
            cx = x0 + i * (w / len(data)) + w / (len(data) * 2)
            lbl = data[i]["date"][5:]
            painter.drawText(QRectF(cx - 22, y0 + h + 6, 44, 14), Qt.AlignCenter, lbl)


# ─── 启动 ────────────────────────────────────

def launch():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # 关闭窗口后不退出进程，托盘仍驻留
    app.setQuitOnLastWindowClosed(False)
    icon_path = str(PROJECT_DIR / "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()
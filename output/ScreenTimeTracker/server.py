"""
屏幕使用时间 - Web 面板 (Flask)
本地端口 19999，所有前端资源内嵌，不依赖外部 CDN
"""

import os
import sys
import json
import sqlite3
import base64
import math
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__)
PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "screen_time.db"

# ─── 数据库工具 ────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def stats_for_date(target_date):
    """获取某天的摘要和进程使用数据"""
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
        "date": d,
        "total_active_seconds": total_active,
        "total_idle_seconds": total_idle,
        "notification_count": summary['notification_count'] if summary else 0,
        "notification_sources": json.loads(summary['notification_sources']) if summary and summary['notification_sources'] else {},
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


def samples_for_date(target_date):
    """获取某天的采样数据（用于24小时时间轴）"""
    conn = get_db()
    d = target_date.isoformat() if isinstance(target_date, date) else target_date
    rows = conn.execute(
        "SELECT timestamp, process_name, is_foreground FROM usage_samples WHERE date(timestamp)=? ORDER BY timestamp",
        (d,)
    ).fetchall()
    conn.close()
    return [{"timestamp": r["timestamp"], "process_name": r["process_name"], "is_foreground": r["is_foreground"]} for r in rows]


def days_with_data():
    """返回有数据的所有日期"""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT date FROM daily_summary ORDER BY date").fetchall()
    conn.close()
    return [r["date"] for r in rows]


# ─── API ──────────────────────────────────────

@app.route("/api/today")
def api_today():
    return jsonify(stats_for_date(date.today()))


@app.route("/api/date/<d>")
def api_date(d):
    return jsonify(stats_for_date(d))


@app.route("/api/samples/<d>")
def api_samples(d):
    return jsonify(samples_for_date(d))


@app.route("/api/range")
def api_range():
    """获取一个日期范围内的每日摘要"""
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    conn = get_db()
    rows = conn.execute(
        "SELECT date, total_active_seconds, notification_count FROM daily_summary WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end)
    ).fetchall()
    conn.close()
    return jsonify([{
        "date": r["date"],
        "total_active_seconds": r["total_active_seconds"],
        "notification_count": r["notification_count"]
    } for r in rows])


@app.route("/api/dates")
def api_dates():
    return jsonify(days_with_data())


# ─── 前端 HTML ───────────────────────────────

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>屏幕使用时间</title>
<style>
:root {
    --bg: #f2f2f7;
    --card-bg: #ffffff;
    --accent: #5e5ce6;
    --accent2: #30d158;
    --accent3: #ff9f0a;
    --accent4: #ff375f;
    --text: #1c1c1e;
    --text2: #8e8e93;
    --sep: #e5e5ea;
    --radius: 16px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}
.container { max-width: 800px; margin: 0 auto; padding: 24px 20px 40px; }

/* 头部 */
.header { text-align: center; margin: 20px 0 10px; }
.header h1 { font-size: 34px; font-weight: 700; letter-spacing: -0.5px; }
.header h1 span { color: var(--accent); }
.date-sub { font-size: 14px; color: var(--text2); margin-top: 6px; }

/* 概要卡片 */
.summary-cards { display: flex; gap: 12px; margin: 24px 0; }
.summary-card {
    flex: 1; background: var(--card-bg); border-radius: var(--radius);
    padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.04);
    text-align: center;
}
.summary-card .value { font-size: 28px; font-weight: 700; }
.summary-card .label { font-size: 12px; color: var(--text2); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.summary-card.accent .value { color: var(--accent); }
.summary-card.accent2 .value { color: var(--accent4); }
.summary-card.accent3 .value { color: var(--accent3); }

/* 空状态 */
.empty-state {
    text-align: center; padding: 60px 20px; color: var(--text2);
}
.empty-state .icon { font-size: 64px; margin-bottom: 16px; opacity: 0.5; }
.empty-state h3 { font-size: 20px; margin-bottom: 8px; color: var(--text); }
.empty-state p { font-size: 15px; max-width: 400px; margin: 0 auto 4px; }

/* 时间范围选择器 */
.segmented { display: flex; background: #e5e5ea; border-radius: 9px; padding: 2px; margin: 20px 0; }
.segmented button {
    flex: 1; border: none; background: none; padding: 8px 0;
    font-size: 14px; font-weight: 500; color: var(--text); border-radius: 7px;
    cursor: pointer; transition: all 0.2s;
}
.segmented button.active { background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }

/* 时间轴 */
.timeline { margin: 16px 0 8px; }
.timeline canvas { width: 100%; border-radius: var(--radius); background: var(--card-bg); padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }

/* 排行榜 */
.rank-list { background: var(--card-bg); border-radius: var(--radius); overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.rank-header {
    display: flex; align-items: center; padding: 16px 20px 10px;
    font-size: 13px; color: var(--text2); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.rank-header .name { flex: 1; }
.rank-header .stat { width: 80px; text-align: right; }
.rank-header .stat2 { width: 70px; text-align: right; }

.rank-item {
    display: flex; align-items: center; padding: 12px 20px;
    border-top: 1px solid var(--sep); transition: background 0.15s;
    cursor: default;
}
.rank-item:hover { background: #f9f9fb; }
.rank-item .icon {
    width: 32px; height: 32px; border-radius: 8px; margin-right: 12px;
    background: #e8e8ed; display: flex; align-items: center; justify-content: center;
    font-size: 16px; overflow: hidden;
}
.rank-item .icon img { width: 28px; height: 28px; object-fit: contain; }
.rank-item .info { flex: 1; }
.rank-item .info .pname { font-size: 15px; font-weight: 500; }
.rank-item .info .detail { font-size: 12px; color: var(--text2); margin-top: 2px; }
.rank-item .time { width: 80px; text-align: right; font-weight: 600; font-size: 15px; }
.rank-item .opens { width: 70px; text-align: right; font-size: 14px; color: var(--text2); }

/* 进度条 */
.progress-bar { height: 3px; background: #e5e5ea; border-radius: 2px; margin-top: 4px; overflow: hidden; }
.progress-bar .fill { height: 100%; border-radius: 2px; background: var(--accent); transition: width 1s ease; }

/* 使用建议 */
.advice-card {
    background: var(--card-bg); border-radius: var(--radius); padding: 20px;
    margin: 24px 0; box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.advice-card h3 { font-size: 18px; margin-bottom: 12px; }
.advice-card ul { padding-left: 20px; color: var(--text2); line-height: 1.8; font-size: 14px; }

/* 响应式 */
@media (max-width: 600px) {
    .summary-cards { flex-direction: column; }
    .container { padding: 12px 12px 40px; }
    .header h1 { font-size: 28px; }
}

/* 通知来源标签 */
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-right: 4px; margin-bottom: 4px; background: #f0f0f5; color: var(--text2); }
.tag.fg { background: #d4f5dd; color: #1c7d30; }
.tag.bg { background: #e8e8ed; color: #636366; }

/* 加载动画 */
@keyframes pulse {
    0%,100% { opacity: 1; }
    50% { opacity: 0.5; }
}
.loading { animation: pulse 1.5s infinite; }
</style>
</head>
<body>
<div class="container" id="app">
    <div class="header">
        <h1><span>屏幕</span>使用时间</h1>
        <div class="date-sub" id="dateSub"></div>
    </div>

    <div id="emptyBox"></div>

    <div class="summary-cards" id="summaryCards" style="display:none">
        <div class="summary-card accent">
            <div class="value" id="vActive">--</div>
            <div class="label">活跃时间</div>
        </div>
        <div class="summary-card accent2">
            <div class="value" id="vOpens">--</div>
            <div class="label">软件打开次数</div>
        </div>
        <div class="summary-card accent3">
            <div class="value" id="vNotifs">--</div>
            <div class="label">通知数</div>
        </div>
    </div>

    <div class="segmented" id="segmented" style="display:none">
        <button data-mode="1d" class="active">今天</button>
        <button data-mode="7d">本周</button>
        <button data-mode="30d">本月</button>
    </div>

    <div class="timeline" id="timelineWrap" style="display:none">
        <canvas id="timelineCanvas" height="180"></canvas>
    </div>

    <div class="rank-list" id="rankList" style="display:none">
        <div class="rank-header"><span class="name">软件</span><span class="stat">使用时长</span><span class="stat2">打开次数</span></div>
        <div id="rankItems"></div>
    </div>

    <div class="advice-card" id="adviceCard" style="display:none">
        <h3>使用建议</h3>
        <div id="adviceContent"></div>
    </div>
</div>

<script>
// ========== 全局状态 ==========
let currentMode = '1d';
let todayData = null;
let rangeData = [];
let allDates = [];
let iconsCache = {};

// ========== 格式化 ==========
function fmtTime(s) {
    s = Math.round(s);
    if (s < 60) return s + '秒';
    var m = Math.floor(s / 60);
    var h = Math.floor(m / 60);
    m = m % 60;
    if (h > 0) return h + '小时' + (m > 0 ? ' ' + m + '分' : '');
    return m + '分钟';
}

function fmtShort(s) {
    s = Math.round(s);
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    var h = Math.floor(m / 60);
    m = m % 60;
    if (h > 0) return h + 'h' + (m > 0 ? ' ' + m + 'm' : '');
    return m + 'm';
}

// ========== API ==========
async function fetchApi(url) {
    var r = await fetch(url);
    return r.json();
}

// ========== 渲染 ==========
function showEmpty(msg) {
    document.getElementById('emptyBox').innerHTML =
        '<div class="empty-state"><div class="icon">&#x23F0;</div><h3>暂无数据</h3><p>' + msg + '</p></div>';
    document.getElementById('summaryCards').style.display = 'none';
    document.getElementById('segmented').style.display = 'none';
    document.getElementById('timelineWrap').style.display = 'none';
    document.getElementById('rankList').style.display = 'none';
    document.getElementById('adviceCard').style.display = 'none';
}

function renderOverview(data) {
    todayData = data;
    document.getElementById('emptyBox').innerHTML = '';
    document.getElementById('summaryCards').style.display = 'flex';
    document.getElementById('segmented').style.display = 'flex';
    document.getElementById('timelineWrap').style.display = 'block';
    document.getElementById('rankList').style.display = 'block';

    var total = data.total_active_seconds || 0;
    document.getElementById('vActive').textContent = fmtTime(total);
    var totalOpens = 0;
    data.processes.forEach(function(p) { totalOpens += (p.open_count || 0); });
    document.getElementById('vOpens').textContent = totalOpens;
    document.getElementById('vNotifs').textContent = data.notification_count || 0;

    if (currentMode === '1d') {
        document.getElementById('dateSub').textContent =
            (new Date()).toLocaleDateString('zh-CN', {weekday:'long', year:'numeric', month:'long', day:'numeric'});
    } else {
        document.getElementById('dateSub').textContent =
            (currentMode === '7d') ? '最近 7 天汇总' : '最近 30 天汇总';
    }

    renderProcessList(data.processes, total);
    drawTimeline();

    // 建议
    if (allDates.length >= 3) {
        document.getElementById('adviceCard').style.display = 'block';
        renderAdvice();
    } else if (allDates.length > 0) {
        document.getElementById('adviceCard').style.display = 'block';
        document.getElementById('adviceContent').innerHTML =
            '<p style="color:var(--text2)">数据不足3天，再用几天才能给出个性化建议。</p>';
    }
}

function renderProcessList(processes, total) {
    var html = '';
    var maxFg = 0;
    processes.forEach(function(p) { if (p.foreground_seconds > maxFg) maxFg = p.foreground_seconds; });

    processes.forEach(function(p) {
        var totalSec = (p.foreground_seconds || 0) + (p.background_seconds || 0);
        if (totalSec < 5) return;
        var barW = maxFg > 0 ? ((p.foreground_seconds || 0) / maxFg * 100) : 0;
        var iconHtml = getIconHtml(p.name);
        html +=
            '<div class="rank-item">' +
            '<div class="icon">' + iconHtml + '</div>' +
            '<div class="info">' +
            '<div class="pname">' + escHtml(p.name) + '</div>' +
            '<div class="detail">' +
            '<span class="tag fg">前台 ' + fmtShort(p.foreground_seconds || 0) + '</span>' +
            '<span class="tag bg">后台 ' + fmtShort(p.background_seconds || 0) + '</span>' +
            (p.notification_count > 0 ? '<span class="tag">通知 ' + p.notification_count + '</span>' : '') +
            '</div>' +
            '<div class="progress-bar"><div class="fill" style="width:' + barW + '%"></div></div>' +
            '</div>' +
            '<div class="time">' + fmtShort(totalSec) + '</div>' +
            '<div class="opens">' + (p.open_count || 0) + '次</div>' +
            '</div>';
    });
    document.getElementById('rankItems').innerHTML = html || '<div style="padding:20px;color:var(--text2);text-align:center;">暂无进程数据</div>';
}

function getIconHtml(name) {
    var key = name.toLowerCase();
    if (iconsCache[key]) return '<img src="' + iconsCache[key] + '">';
    // 尝试获取图标
    fetch('/api/icon/' + encodeURIComponent(name)).then(function(r) { return r.json(); }).then(function(d) {
        if (d.icon) { iconsCache[key] = 'data:image/png;base64,' + d.icon; refreshIcon(name); }
    }).catch(function(){});
    return '<span style="color:#999">#' + name.slice(0,1).toUpperCase() + '</span>';
}

function refreshIcon(name) {
    var items = document.querySelectorAll('.rank-item .pname');
    items.forEach(function(el) {
        if (el.textContent === name) {
            var iconEl = el.parentElement.parentElement.querySelector('.icon');
            iconEl.innerHTML = '<img src="' + iconsCache[name.toLowerCase()] + '">';
        }
    });
}

function escHtml(s) { var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

// ========== 时间轴 ==========
function drawTimeline() {
    var canvas = document.getElementById('timelineCanvas');
    var ctx = canvas.getContext('2d');
    var W = canvas.parentElement.clientWidth - 4;
    var H = 180;
    canvas.width = W * (window.devicePixelRatio || 1);
    canvas.height = H * (window.devicePixelRatio || 1);
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

    ctx.clearRect(0, 0, W, H);

    // 网格线
    ctx.strokeStyle = '#e5e5ea';
    ctx.lineWidth = 0.5;
    for (var i = 1; i < 4; i++) {
        var y = 30 + i * 30;
        ctx.beginPath(); ctx.moveTo(50, y); ctx.lineTo(W - 20, y); ctx.stroke();
    }
    for (var h = 0; h <= 1; h++) { ctx.fillStyle = '#8e8e93'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right'; ctx.fillText(h + 'h', 45, 152 - h*60); }

    if (currentMode === '1d') {
        fetchApi('/api/samples/' + (new Date()).toISOString().slice(0,10)).then(function(samples) {
            drawDayTimeline(ctx, W, H, samples);
        });
    } else {
        var start = currentMode === '7d' ? getDateStr(-6) : getDateStr(-29);
        var end = getDateStr(0);
        fetchApi('/api/range?start=' + start + '&end=' + end).then(function(data) {
            rangeData = data;
            drawRangeTimeline(ctx, W, H, data);
        });
    }
}

function getDateStr(offset) {
    var d = new Date(); d.setDate(d.getDate() + offset);
    return d.toISOString().slice(0,10);
}

function drawDayTimeline(ctx, W, H, samples) {
    if (!samples || samples.length === 0) {
        ctx.fillStyle = '#8e8e93'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('暂无采样数据', W/2, H/2); return;
    }
    // 按小时聚合
    var hours = new Array(24).fill(0);
    samples.forEach(function(s) {
        var h = parseInt(s.timestamp.slice(11,13));
        if (s.is_foreground) hours[h] += 5;
    });
    var maxVal = Math.max(3600, Math.max.apply(null, hours));
    var barW = Math.max(2, (W - 70) / 24 - 2);
    for (var i = 0; i < 24; i++) {
        var barH = (hours[i] / maxVal) * 90;
        var x = 50 + i * ((W - 70) / 24) + 1;
        var gradient = ctx.createLinearGradient(x, 150 - barH, x, 150);
        gradient.addColorStop(0, '#5e5ce6');
        gradient.addColorStop(1, '#5e5ce640');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        roundedRect(ctx, x, 150 - barH, barW, barH, 2);
        ctx.fill();
        if (i % 3 === 0) {
            ctx.fillStyle = '#8e8e93'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(i + ':00', x + barW/2, 165);
        }
    }
}

function drawRangeTimeline(ctx, W, H, data) {
    if (!data || data.length === 0) {
        ctx.fillStyle = '#8e8e93'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('暂无数据', W/2, H/2); return;
    }
    var maxVal = Math.max(3600, Math.max.apply(null, data.map(function(d) { return d.total_active_seconds || 0; })));
    var barW = Math.max(3, (W - 70) / data.length - 2);
    data.forEach(function(d, i) {
        var val = d.total_active_seconds || 0;
        var barH = Math.max(2, (val / maxVal) * 90);
        var x = 50 + i * ((W - 70) / data.length) + 1;
        var gradient = ctx.createLinearGradient(x, 150 - barH, x, 150);
        gradient.addColorStop(0, '#5e5ce6');
        gradient.addColorStop(1, '#5e5ce640');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        roundedRect(ctx, x, 150 - barH, barW, barH, 2);
        ctx.fill();
        if (i % Math.ceil(data.length / 10) === 0 || data.length <= 10) {
            ctx.fillStyle = '#8e8e93'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(d.date.slice(5), x + barW/2, 168);
        }
    });
}

function roundedRect(ctx, x, y, w, h, r) {
    if (h < r*2) r = h/2; if (w < r*2) r = w/2;
    ctx.moveTo(x+r, y); ctx.lineTo(x+w-r, y); ctx.quadraticCurveTo(x+w, y, x+w, y+r);
    ctx.lineTo(x+w, y+h-r); ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
    ctx.lineTo(x+r, y+h); ctx.quadraticCurveTo(x, y+h, x, y+h-r);
    ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y); ctx.closePath();
}

// ========== 建议 ==========
function renderAdvice() {
    var tips = [];
    var d = todayData;
    var totalSec = d.total_active_seconds || 0;
    var totalMin = Math.round(totalSec / 60);
    var procs = d.processes || [];

    // 与历史平均对比
    if (allDates.length >= 3) {
        fetchApi('/api/range?start=' + allDates[Math.max(0, allDates.length - 4)] + '&end=' + allDates[allDates.length - 2])
            .then(function(hist) {
                var avg = 0;
                hist.forEach(function(h) { avg += h.total_active_seconds; });
                avg = avg / Math.max(1, hist.length);
                var moreTips = [];
                if (totalSec > avg * 1.5 && totalMin > 60) {
                    moreTips.push('今天使用时间比平时多了约 ' + Math.round((totalSec/avg - 1)*100) + '%，注意适当休息眼睛');
                }
                if (totalSec < avg * 0.5 && totalMin > 0) {
                    moreTips.push('今天使用时间比平时少很多，继续保持');
                }

                // 晚上10点后娱乐软件
                var now = new Date();
                if (now.getHours() >= 22) {
                    var entKey = ['chrome.exe', 'msedge.exe', 'steam.exe', 'firefox.exe', 'bilibili', 'qq.exe', 'wechat.exe'];
                    var entTime = 0;
                    procs.forEach(function(p) {
                        var n = p.name.toLowerCase();
                        entKey.forEach(function(k) { if (n.indexOf(k) >= 0) entTime += p.foreground_seconds; });
                    });
                    if (entTime > 1800) {
                        moreTips.push('晚上10点后娱乐软件使用超过30分钟，建议早点休息');
                    }
                }

                // 单软件异常
                procs.forEach(function(p) {
                    if ((p.foreground_seconds || 0) > 7200 && p.name.indexOf('exe') >= 0) {
                        moreTips.push('"' + p.name + '" 今天前台使用超过2小时，可以适当休息一下');
                    }
                });

                renderAdviceList(moreTips);
            });
    }
}

function renderAdviceList(tips) {
    if (!tips || tips.length === 0) {
        tips = ['今天的使用习惯良好，没有特别需要注意的地方。'];
    }
    var html = '<ul>';
    tips.forEach(function(t) { html += '<li>' + t + '</li>'; });
    html += '</ul>';
    document.getElementById('adviceContent').innerHTML = html;
}

// ========== 模式切换 ==========
document.getElementById('segmented').addEventListener('click', function(e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    document.querySelectorAll('.segmented button').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentMode = btn.dataset.mode;
    updateView();
});

function updateView() {
    if (currentMode === '1d') {
        fetchApi('/api/today').then(function(d) { renderOverview(d); });
    } else if (currentMode === '7d' || currentMode === '30d') {
        fetchApi('/api/dates').then(function(dates) {
            allDates = dates;
            var days = currentMode === '7d' ? 7 : 30;
            var start = getDateStr(-(days-1));
            var end = getDateStr(0);
            fetchApi('/api/range?start=' + start + '&end=' + end).then(function(data) {
                rangeData = data;
                var merged = { date: start + ' ~ ' + end, total_active_seconds: 0, total_idle_seconds: 0, notification_count: 0, processes: [] };
                var procMap = {};
                data.forEach(function(d) {
                    merged.total_active_seconds += d.total_active_seconds;
                    merged.notification_count += d.notification_count;
                });
                // 获取每天进程汇总
                var promises = dates.filter(function(d) { return d >= start && d <= end; }).map(function(d) { return fetchApi('/api/date/' + d); });
                Promise.all(promises).then(function(results) {
                    var procMap = {};
                    results.forEach(function(r) {
                        r.processes.forEach(function(p) {
                            var key = p.name;
                            if (!procMap[key]) procMap[key] = { name: p.name, foreground_seconds: 0, background_seconds: 0, open_count: 0, notification_count: 0 };
                            procMap[key].foreground_seconds += p.foreground_seconds;
                            procMap[key].background_seconds += p.background_seconds;
                            procMap[key].open_count += p.open_count;
                            procMap[key].notification_count += p.notification_count;
                        });
                    });
                    merged.processes = Object.values(procMap).sort(function(a,b) { return (b.foreground_seconds+b.background_seconds) - (a.foreground_seconds+a.background_seconds); });
                    document.getElementById('dateSub').textContent =
                        (currentMode === '7d') ? '最近 7 天汇总' : '最近 30 天汇总';
                    renderOverview(merged);
                });
            });
        });
    }
}

// ========== 启动 ==========
async function init() {
    allDates = await fetchApi('/api/dates');
    if (allDates.length === 0) {
        showEmpty('追踪器已启动，正在收集使用数据。请稍等片刻后刷新页面。');
    } else {
        updateView();
    }
    setInterval(updateView, 5000);
}

init();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return INDEX_HTML


# ─── 图标 API ─────────────────────────────────

import subprocess
import tempfile

@app.route("/api/icon/<proc_name>")
def api_icon(proc_name):
    """获取进程图标 base64"""
    # 尝试从进程路径获取图标
    try:
        import win32ui
        import win32gui
        import win32con
        import win32api
        from PIL import Image
        import io

        for proc in psutil.process_iter(['name', 'exe']):
            try:
                pname = proc.info['name']
                if pname and pname.lower() == proc_name.lower():
                    exe = proc.info['exe']
                    if exe and os.path.exists(exe):
                        ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                        ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
                        large, small = win32gui.ExtractIconEx(exe, 0)
                        hicon = None
                        if large:
                            hicon = large[0]
                        elif small:
                            hicon = small[0]
                        if not hicon:
                            break
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
                            buf = io.BytesIO()
                            img.save(buf, format='PNG')
                            icon_b64 = base64.b64encode(buf.getvalue()).decode()
                            for h in large:
                                win32gui.DestroyIcon(h)
                            for h in small:
                                win32gui.DestroyIcon(h)
                            win32gui.DeleteObject(hbmp.GetHandle())
                            memdc.DeleteDC()
                            hdc.DeleteDC()
                            return jsonify({"icon": icon_b64})
                        finally:
                            pass
                    break
            except Exception:
                pass
    except ImportError:
        pass
    return jsonify({"icon": None})


# ─── 启动 ─────────────────────────────────────

def start_server():
    print(f"屏幕使用时间面板已启动: http://127.0.0.1:19999")
    app.run(host="127.0.0.1", port=19999, debug=False)


if __name__ == "__main__":
    start_server()
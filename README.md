# 屏幕使用时间 (Screen Time Tracker)

类似 iPhone「屏幕使用时间」的 Windows 桌面端追踪工具。

## 功能

- **真实活动追踪**：基于键盘鼠标空闲检测（5分钟无操作算离开），不统计离开时间
- **进程级统计**：前台/后台使用时间分开统计，同进程多窗口合并
- **Windows 通知统计**：读取系统通知数据库，按来源软件汇总
- **历史数据**：SQLite 本地存储，支持今日/本周/本月切换查看
- **iOS 风格面板**：Flask Web 界面，时间轴可视化，5 秒自动刷新
- **使用建议**：基于真实数据对比，数据不足 3 天时明确告知

## 快速开始

```bash
pip install psutil flask pywin32 pillow
python tracker.py      # 后台采集（pythonw 静默运行）
python server.py        # Web 面板 (http://127.0.0.1:19999)
python start.py         # 一键启动采集+面板
python start.py --panel # 仅打开面板（采集已在后台时）
```

## 桌面快捷方式

安装后桌面上有两个快捷方式：

| 快捷方式 | 功能 |
|---------|------|
| 屏幕使用时间 | 启动采集 + 打开面板 |
| 屏幕使用时间面板 | 仅打开面板 |

## 技术栈

- Python 3.11+
- 采集：psutil + win32api + ctypes (GetLastInputInfo)
- 存储：SQLite (WAL 模式)
- 面板：Flask + 内嵌 HTML/CSS/JS
- 图标：Pillow 生成多尺寸 ICO

## 项目结构

```
ScreenTimeTracker/
├── tracker.py        # 后台采集模块
├── server.py         # Web 面板 (Flask + 内嵌前端)
├── start.py          # 启动脚本
├── generate_icon.py  # 图标生成
└── icon.ico          # 应用图标
```
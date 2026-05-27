# 屏幕使用时间 (Screen Time Tracker)

类似 iPhone「屏幕使用时间」的 Windows **桌面应用**：后台采集 + iOS 风格原生 UI，常驻系统托盘，不依赖浏览器。

## 功能

- **真实活动追踪**：基于键盘鼠标空闲检测（5 分钟无操作算离开），不统计离开时间
- **进程级统计**：前台/后台使用时间分开统计，同进程多窗口合并
- **Windows 通知统计**：读取系统通知数据库，按来源软件汇总
- **历史数据**：SQLite 本地存储，支持今日/本周/本月切换查看
- **iOS 风格原生面板**：PySide6 桌面窗口，时间轴可视化，5 秒自动刷新
- **系统托盘常驻**：关闭窗口最小化到托盘，单击托盘图标切换显示
- **使用建议**：基于真实数据对比，数据不足 3 天时明确告知

## 快速开始

```bash
pip install psutil PySide6 pywin32 pillow

cd output/ScreenTimeTracker
python start.py            # 启动采集（后台）+ 桌面 UI
python start.py --ui       # 仅打开桌面 UI（采集已在后台时）
python start.py --tracker  # 仅启动后台采集
```

也可以直接跑入口脚本：

```bash
python desktop_ui.py   # 单独运行 UI（不启动采集）
python tracker.py      # 单独运行采集（pythonw 可静默）
python launcher.py     # 采集 + UI 同进程运行（PyInstaller 打包用）
```

## 打包成 exe

```bash
cd output/ScreenTimeTracker
python build_release.py
```

会在 `release/` 下生成：

| 文件 | 说明 |
|---|---|
| `ScreenTimeTracker_Portable_v*.zip` | 便携版：解压即用 |
| `ScreenTimeTracker_Setup_v*.zip` | 安装版：含 Install.ps1 / Uninstall.ps1 |

安装版会在桌面创建快捷方式「屏幕使用时间」。

## 技术栈

- Python 3.11+
- 桌面 UI：PySide6（Qt 6）+ 系统托盘（QSystemTrayIcon）
- 采集：psutil + win32api + ctypes (GetLastInputInfo)
- 存储：SQLite (WAL 模式)
- 打包：PyInstaller（单 exe）
- 图标：Pillow 生成多尺寸 ICO

## 项目结构

```
output/ScreenTimeTracker/
├── desktop_ui.py            # 桌面 UI（PySide6，含系统托盘）
├── tracker.py               # 后台采集
├── launcher.py              # 打包入口：采集线程 + UI 主线程
├── start.py                 # 源码运行入口（启动两端独立进程）
├── build_release.py         # 打包脚本（生成便携版/安装版）
├── generate_icon.py         # 图标生成
├── ScreenTimeTracker.spec   # PyInstaller 配置
└── icon.ico                 # 应用图标
```

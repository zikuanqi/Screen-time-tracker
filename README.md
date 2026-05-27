# 屏幕使用时间 (Screen Time Tracker)

类似 iPhone「屏幕使用时间」的 Windows **桌面应用**：后台采集 + iOS 风格原生 UI，常驻系统托盘，不依赖浏览器。

## 功能

- **真实活动追踪**：基于键盘鼠标空闲检测（5 分钟无操作算离开），不统计离开时间
- **进程级统计**：前台/后台使用时间分开统计，同进程多窗口合并
- **Windows 通知统计**：读取系统通知数据库，按来源软件汇总
- **历史数据**：SQLite 本地存储，支持今日/本周/本月切换查看
- **iOS 风格原生面板**：PySide6 桌面窗口，时间轴可视化，5 秒自动刷新
- **系统托盘常驻**：关闭窗口最小化到托盘，单击托盘图标切换显示，右键菜单退出
- **使用建议**：基于真实数据对比，数据不足 3 天时明确告知

## 系统要求

- Windows 10 / 11
- 普通用户权限即可（读 Windows 通知数据库不需要管理员）

---

## 下载使用（推荐）

直接用打包好的单文件 exe，无需安装 Python。

```bash
cd output/ScreenTimeTracker
python build_release.py
```

生成的产物在 `output/ScreenTimeTracker/release/`：

| 文件 | 说明 |
|---|---|
| `ScreenTimeTracker_Portable_v*.zip` | 便携版：解压即用，双击 `ScreenTimeTracker.exe` 启动 |
| `ScreenTimeTracker_Setup_v*.zip` | 安装版：含 `Install.ps1` / `Uninstall.ps1`，自动建桌面快捷方式 |

启动后：

- 窗口出现 + 右下角系统托盘多一个图标
- 点 **窗口右上角 ×** = 最小化到托盘（程序继续在后台采集）
- **右键托盘图标 → 退出** 才是真正结束
- 数据库 `screen_time.db` 与 exe 同目录（便携版）或在安装目录（安装版）

---

## 源码运行（开发者）

```bash
pip install psutil PySide6 pywin32 pillow

cd output/ScreenTimeTracker
python start.py            # 启动采集（后台）+ 桌面 UI
python start.py --ui       # 仅打开桌面 UI（采集已在后台时）
python start.py --tracker  # 仅启动后台采集
```

`start.py` 会用 `pythonw.exe + DETACHED_PROCESS` 派生两个完全独立的进程，关闭终端不影响。也可以直接跑各入口脚本：

```bash
python desktop_ui.py   # 单独运行 UI（不启动采集）
python tracker.py      # 单独运行采集（pythonw 可静默）
python launcher.py     # 采集 + UI 同进程运行（PyInstaller 打包入口）
```

## 故障排查

- **双击 exe 没反应 / 窗口闪一下就消失**：看 exe 所在目录的 `desktop_ui_error.log`，里面有完整的异常堆栈（程序里装了 `sys.excepthook` 把崩溃写到这个文件）。
- **托盘里找不到图标**：Windows 默认会把新应用的托盘图标折叠到「显示隐藏的图标」（^ 箭头）里，点开就能看到，右键可以拖到常显区。
- **数据没在更新**：确认 tracker 进程在跑：`tasklist | findstr ScreenTimeTracker`（exe）或 `tasklist | findstr pythonw`（源码模式）。

## 技术栈

- Python 3.11+
- 桌面 UI：PySide6（Qt 6）+ 系统托盘（QSystemTrayIcon）
- 采集：psutil + win32api + ctypes (GetLastInputInfo)
- 存储：SQLite (WAL 模式)
- 打包：PyInstaller 6.x（单 exe）
- 图标：Pillow 生成多尺寸 ICO

## 项目结构

```
output/ScreenTimeTracker/
├── desktop_ui.py            # 桌面 UI（PySide6，含系统托盘 + 异常日志）
├── tracker.py               # 后台采集
├── launcher.py              # 打包入口：采集线程 + UI 主线程
├── start.py                 # 源码运行入口（pythonw + DETACHED_PROCESS）
├── build_release.py         # 打包脚本（生成便携版/安装版）
├── generate_icon.py         # 图标生成
├── ScreenTimeTracker.spec   # PyInstaller 配置
└── icon.ico                 # 应用图标
```

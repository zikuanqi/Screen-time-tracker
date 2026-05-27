# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 项目根目录（PyInstaller 6.x 的 spec 执行上下文不再定义 __file__，改用 SPEC）
project_dir = Path(SPEC).resolve().parent

# 添加项目路径到 sys.path
sys.path.insert(0, str(project_dir))

# 隐藏控制台窗口
console = False

# 单文件打包
a = Analysis(
    ['launcher.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        # 图标文件
        (str(project_dir / 'icon.ico'), '.'),
        # 数据库模板（空）
        (str(project_dir / 'screen_time.db'), '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'psutil',
        'win32gui',
        'win32process',
        'win32api',
        'win32con',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy',  # 科学计算库
        'tkinter', 'PyQt5', 'PyQt6',  # 其他 GUI
        'django', 'flask', 'tornado',  # Web 框架
        'pytest', 'unittest',  # 测试框架
    ],
    noarchive=False,
)

# 打包选项
pyz = PYZ(a.pure, a.zipped_data)

# 单文件 exe
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ScreenTimeTracker',
    debug=False,
    bootloader_ignore_signals=True,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x64',
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / 'icon.ico'),
)

# 收集所有文件到 dist
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ScreenTimeTracker',
)
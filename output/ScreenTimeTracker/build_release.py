"""
屏幕使用时间 - 打包脚本
生成可执行文件，用于 GitHub Release
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent
DIST_DIR = PROJECT_DIR / "dist"
RELEASE_DIR = PROJECT_DIR / "release"
BUILD_DIR = PROJECT_DIR / "build"

# 清理
def clean():
    for d in [DIST_DIR, RELEASE_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    for f in PROJECT_DIR.glob("*.spec"):
        if f.name != "ScreenTimeTracker.spec":
            f.unlink(missing_ok=True)
    print("清理完成")

# PyInstaller 打包
def build_exe():
    spec = PROJECT_DIR / "ScreenTimeTracker.spec"
    if not spec.exists():
        print("错误: 未找到 spec 文件")
        return False

    print("开始打包...")
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", str(spec)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print(f"打包失败:\n{result.stderr}")
        return False
    print("打包成功")
    return True

# 创建便携版 zip
def create_portable_zip():
    exe_path = DIST_DIR / "ScreenTimeTracker" / "ScreenTimeTracker.exe"
    if not exe_path.exists():
        print("错误: 未找到可执行文件")
        return None

    # 创建 release 目录
    RELEASE_DIR.mkdir(exist_ok=True)

    # 便携版 zip
    version = datetime.now().strftime("%Y%m%d")
    zip_name = f"ScreenTimeTracker_Portable_v{version}.zip"
    zip_path = RELEASE_DIR / zip_name

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 主程序
        zf.write(exe_path, "ScreenTimeTracker.exe")
        # README
        readme = PROJECT_DIR / "README.md"
        if readme.exists():
            zf.write(readme, "README.txt")
        # 快捷说明
        zf.writestr("使用说明.txt", """屏幕使用时间追踪工具 - 便携版

双击 ScreenTimeTracker.exe 启动
- 自动后台采集使用数据
- 桌面显示 iOS 风格界面
- 数据保存在程序同目录的 screen_time.db

功能：
- 实时活跃时间/打开次数/通知数统计
- 按小时时间轴图表
- 进程使用时长排行
- 智能使用建议
- 今日/本周/本月切换

退出：关闭窗口或右键系统托盘图标
""")

    print(f"便携版创建完成: {zip_path.name}")
    return zip_path

# 创建安装版（含卸载器）
def create_installer():
    # 简单安装包：exe + 卸载脚本
    exe_path = DIST_DIR / "ScreenTimeTracker" / "ScreenTimeTracker.exe"
    if not exe_path.exists():
        print("错误: 未找到可执行文件")
        return None

    version = datetime.now().strftime("%Y%m%d")
    install_name = f"ScreenTimeTracker_Setup_v{version}.zip"
    install_path = RELEASE_DIR / install_name

    # 创建安装目录结构
    temp_install = RELEASE_DIR / "temp_install"
    if temp_install.exists():
        shutil.rmtree(temp_install)
    temp_install.mkdir()

    # 复制 exe
    shutil.copy2(exe_path, temp_install / "ScreenTimeTracker.exe")

    # 创建卸载脚本
    uninstall_ps1 = temp_install / "Uninstall.ps1"
    uninstall_ps1.write_text("""# 卸载脚本
Write-Host "正在卸载屏幕使用时间追踪工具..." -ForegroundColor Yellow
$app = Get-Process -Name "ScreenTimeTracker" -ErrorAction SilentlyContinue
if ($app) {
    $app | Stop-Process -Force
    Start-Sleep -Seconds 1
}
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk1 = "$desktop\屏幕使用时间.lnk"
$lnk2 = "$desktop\屏幕使用时间面板.lnk"
if (Test-Path $lnk1) { Remove-Item $lnk1 -Force }
if (Test-Path $lnk2) { Remove-Item $lnk2 -Force }
Write-Host "已删除桌面快捷方式" -ForegroundColor Green
Write-Host "卸载完成" -ForegroundColor Green
""")

    # 创建安装脚本
    install_ps1 = temp_install / "Install.ps1"
    install_ps1.write_text("""# 安装脚本
param(
    [string]$InstallPath = "$env:USERPROFILE\ScreenTimeTracker"
)

Write-Host "正在安装屏幕使用时间追踪工具..." -ForegroundColor Yellow

# 创建安装目录
if (!(Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Path $InstallPath -Force
}

# 复制文件
$sourceDir = $PSScriptRoot
Copy-Item "$sourceDir\ScreenTimeTracker.exe" -Destination $InstallPath -Force

# 创建桌面快捷方式
$WshShell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")

$lnk1 = "$desktop\屏幕使用时间.lnk"
$shortcut1 = $WshShell.CreateShortcut($lnk1)
$shortcut1.TargetPath = "$InstallPath\ScreenTimeTracker.exe"
$shortcut1.WorkingDirectory = $InstallPath
$shortcut1.WindowStyle = 7
$shortcut1.Save()

$lnk2 = "$desktop\屏幕使用时间面板.lnk"
$shortcut2 = $WshShell.CreateShortcut($lnk2)
$shortcut2.TargetPath = "$InstallPath\ScreenTimeTracker.exe"
$shortcut2.WorkingDirectory = $InstallPath
$shortcut2.Arguments = "--ui"
$shortcut2.WindowStyle = 7
$shortcut2.Save()

Write-Host "安装完成！" -ForegroundColor Green
Write-Host "- 程序安装到: $InstallPath" -ForegroundColor Cyan
Write-Host "- 桌面已创建两个快捷方式" -ForegroundColor Cyan
Write-Host "双击「屏幕使用时间」启动完整功能" -ForegroundColor Cyan
""")

    # 打包安装包
    with zipfile.ZipFile(install_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in temp_install.rglob("*"):
            if f.is_file():
                arcname = f.relative_to(temp_install)
                zf.write(f, arcname)

    # 清理临时目录
    shutil.rmtree(temp_install)

    print(f"安装版创建完成: {install_path.name}")
    return install_path

# 主流程
def main():
    print("=== 屏幕使用时间 - 打包工具 ===")
    
    # 1. 清理
    clean()
    
    # 2. 打包 exe
    if not build_exe():
        return
    
    # 3. 创建便携版
    portable = create_portable_zip()
    
    # 4. 创建安装版
    installer = create_installer()
    
    # 5. 汇总
    print("\n=== 打包完成 ===")
    if portable:
        print(f"便携版: {portable}")
    if installer:
        print(f"安装版: {installer}")
    
    # 6. 生成 release 说明
    release_notes = RELEASE_DIR / "release_notes.md"
    release_notes.write_text(f"""# 屏幕使用时间追踪工具 v{datetime.now().strftime('%Y.%m.%d')}

## 功能特性
- 实时追踪屏幕使用时间（活动/空闲检测）
- iOS 风格桌面客户端，无需浏览器
- 进程前台/后台时长统计
- Windows 通知数量统计
- 时间轴图表（今日/本周/本月）
- 智能使用建议
- 系统托盘支持

## 文件说明
- `ScreenTimeTracker_Portable_v*.zip` - 便携版，解压即用
- `ScreenTimeTracker_Setup_v*.zip` - 安装版，含安装/卸载脚本

## 使用方式
### 便携版
1. 解压 zip
2. 双击 `ScreenTimeTracker.exe`
3. 数据保存在同目录 `screen_time.db`

### 安装版
1. 解压 zip
2. 右键 `Install.ps1` → 使用 PowerShell 运行
3. 按提示安装

## 源码
GitHub: https://github.com/zikuanqi/Screen-time-tracker

## 系统要求
- Windows 10/11
- .NET Framework 4.8 (通常已预装)
- 无需 Python 环境

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")
    print(f"发布说明: {release_notes}")

if __name__ == "__main__":
    main()
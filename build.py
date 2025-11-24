#!/usr/bin/env python3
"""
yt-dlp Simple Downloader - Build Script
用 PyInstaller 打包成 Windows 執行檔
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    project_dir = Path(__file__).parent
    
    print("=" * 60)
    print("yt-dlp Simple Downloader - Build Script")
    print("=" * 60)
    print()
    
    # 檢查依賴
    print(" 檢查依賴...")
    try:
        import PyInstaller
        print(" PyInstaller 已安裝")
    except ImportError:
        print("  安裝 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
        print(" PyInstaller 安裝完成")
    
    # 檢查 main.py
    if not (project_dir / "main.py").exists():
        print(" 錯誤：找不到 main.py")
        return 1
    
    print(" main.py 已找到")
    print()
    
    # 開始打包
    print(" 開始打包...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=yt-dlp-downloader",
        "--onefile",
        "--windowed",
        "--collect-all=PyQt5",
        str(project_dir / "main.py")
    ]
    
    result = subprocess.run(cmd, cwd=str(project_dir))
    
    if result.returncode == 0:
        exe_path = project_dir / "dist" / "yt-dlp-downloader.exe"
        if exe_path.exists():
            print()
            print("=" * 60)
            print(" 打包成功！")
            print("=" * 60)
            print(f" 執行檔位置: {exe_path}")
            print(f" 文件大小: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
            print()
            print(" 立即運行:")
            print(f"   {exe_path}")
            print()
            print(" 發佈到社群:")
            print(f"   上傳 {exe_path.name} 到網路社群（GitHub Release、Discord等）")
            print()
            return 0
    
    print(" 打包失敗")
    return 1

if __name__ == "__main__":
    sys.exit(main())

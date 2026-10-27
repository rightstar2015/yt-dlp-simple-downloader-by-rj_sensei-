@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 找不到 .venv，請先依 README 建立 Python 環境。
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -X utf8 build.py
if errorlevel 1 (
    echo 打包失敗；請檢查輸出紀錄或安裝 requirements-build.txt。
    pause
    exit /b 1
)
echo 修正版位於 dist\yt-dlp-downloader.exe
pause

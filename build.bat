 yt-dlp Simple Downloader by Odudins
?

 ???????

??????
   ????
   ????  
   ????
   ????
   ????
   ????

?GUI ???
   ???????900x700?
   ???????ScrollArea?
   ??????
   ??????????
   ?????

??????
   main.py
   requirements.txt
   README.md
   LICENSE (MIT)
   CONTRIBUTING.md
   setup.py
   .gitignore
   .github/copilot-instructions.md
   GITHUB_RELEASE_GUIDE.md
   RELEASE_NOTES.md

??????
   ??????
   ?????
   UTF-8 ????
   ??????



 ????
- ????18.37 KB
- ????10+ ???
- Python?3.8+
- ???3 ??

 ?????

??????????? GitHub?

  git init
  git add .
  git commit -m "Initial commit: yt-dlp Simple Downloader v1.0.0"
  git remote add origin https://github.com/USERNAME/yt-dlp-simple-downloader.git
  git push -u origin main

 ?????@rj_sensei_ (X/Twitter)

' | Out-Host
cd c:\Users\Public\yt-dlp-gui; Get-ChildItem -File | ForEach-Object { "[$(if($_.Name -match 'md|txt|py'){''}else{' '})]] $($_.Name)" }
cd c:\Users\Public\yt-dlp-gui; Get-ChildItem -File | Select-Object Name
cd c:\Users\Public\yt-dlp-gui; ls -Name
cmd /c "cd c:\Users\Public\yt-dlp-gui && dir /b"
cd c:\Users\Public\yt-dlp-gui; .\.venv\Scripts\pip.exe install pyinstaller
cd c:\Users\Public\yt-dlp-gui ; .\.venv\Scripts\pip.exe install pyinstaller 2>&1 | tail -20
cd c:\Users\Public\yt-dlp-gui; .\.venv\Scripts\pip.exe install pyinstaller -q; echo "PyInstaller ????"
cd c:\Users\Public\yt-dlp-gui; powershell -Command ".\.venv\Scripts\pip.exe install pyinstaller" ; Write-Host "????"
cd c:\Users\Public\yt-dlp-gui; @"
# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=['PyQt5'],
             hookspath=[],
             runtime_hooks=[],
             excludedimports=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='yt-dlp-downloader',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='icon.ico')
"@ | Set-Content yt-dlp-downloader.spec -Encoding UTF8
cd c:\Users\Public\yt-dlp-gui; @'
@echo off
REM PyInstaller ????

echo ???? yt-dlp Simple Downloader...
echo.

REM ??????
call .venv\Scripts\activate.bat

REM ?? PyInstaller
pip install pyinstaller -q

REM ??
pyinstaller.exe main.py ^
  --name="yt-dlp-downloader" ^
  --onefile ^
  --windowed ^
  --add-data "." ^
  -i icon.ico 2>nul || pyinstaller.exe main.py ^
  --name="yt-dlp-downloader" ^
  --onefile ^
  --windowed ^
  --add-data "."

echo.
echo ?????
echo ?????: dist\yt-dlp-downloader.exe
echo.
pause

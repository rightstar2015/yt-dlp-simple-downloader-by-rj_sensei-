# 如何發佈到 GitHub 和社群

##  方法 1：發佈 Python 源代碼到 GitHub

### 步驟 1：安裝 Git
- 下載：https://git-scm.com/download/win
- 安裝後重啟 PowerShell

### 步驟 2：上傳到 GitHub

在 `c:\Users\Public\yt-dlp-gui` 目錄打開 PowerShell，執行：

```powershell
# 1. 初始化 Git
git init

# 2. 配置 Git（首次使用）
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 3. 添加所有文件
git add .

# 4. 提交
git commit -m "Initial commit: yt-dlp Simple Downloader v1.0.0"

# 5. 添加遠程倉庫（將 YOUR_USERNAME 改為您的 GitHub 用戶名）
git remote add origin https://github.com/rightstar2015/yt-dlp-simple-downloader-by-rj_sensei-.git

# 6. 重命名主分支
git branch -M main

# 7. 推送到 GitHub
git push -u origin main

# 8. 創建版本標籤
git tag -a v1.0.0 -m "First stable release"
git push origin v1.0.0
```

### 步驟 3：在 GitHub 創建 Release

1. 訪問您的倉庫
2. 點擊 **Releases**  **Create a new release**
3. 選擇標籤 `v1.0.0`
4. 填寫詳情，點擊 **Publish release**

---

##  方法 2：發佈 Windows 執行檔（推薦用於社群分享）

### 自動打包成 EXE

已為您準備了 `build.py` 腳本。執行：

```powershell
cd c:\Users\Public\yt-dlp-gui
.\.venv\Scripts\python.exe build.py
```

執行檔將在 `dist\yt-dlp-downloader.exe` 生成。

### 發佈到社群

**方法 A：GitHub Releases**
1. 在 GitHub 上創建 Release
2. 上傳 `yt-dlp-downloader.exe` 到 Release
3. 分享 Release 頁面鏈接

**方法 B：其他社群**
- Discord：直接上傳或分享下載鏈接
- Twitter/X：分享 GitHub Release 鏈接
- 百度網盤、阿里云盤等：上傳 EXE 文件

---

##  完整檢查清單

### GitHub 發佈
- [ ] 已安裝 Git
- [ ] 已創建 GitHub 帳號
- [ ] 已在 GitHub 創建空倉庫
- [ ] 已執行 `git init` 和 `git add .`
- [ ] 已執行 `git push` 推送代碼
- [ ] 已創建 Release 和標籤

### EXE 發佈
- [ ] 已執行 `build.py` 生成 EXE
- [ ] 已測試 `dist\yt-dlp-downloader.exe`
- [ ] 已上傳到 GitHub Release
- [ ] 已在社群分享鏈接

---

##  推薦社群

| 平台 | 說明 |
|------|------|
| GitHub | 官方倉庫，開源社群 |
| Reddit | r/youtube, r/DataHoarder 等 |
| Discord | 相關技術社群服務器 |
| Twitter/X | @rj_sensei_ 官方帳號推廣 |

---

準備完畢，可以開始發佈了！

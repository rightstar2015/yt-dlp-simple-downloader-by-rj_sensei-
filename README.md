# yt-dlp GUI Downloader 1.1.0

by Odudins。Python／PyQt5 開發的 Windows 影音下載器，MIT License。

## 本版改善

- yt-dlp 更新、FFmpeg 安裝、工具檢查、影片資訊查詢、下載與轉檔全部在背景進行。
- 啟動先顯示視窗，再檢查工具；GitHub 最新版本查詢快取 24 小時。
- 工作可取消，關閉視窗會先停止工作、清理暫存，再安全關閉。
- 影片下載取消時會一併終止其 FFmpeg 子程序，保留完成檔案及可續傳的部分檔案。
- 使用 JSON 取得格式清單與下載進度，支援非數字格式 ID。
- 進階模式可選擇合併影音或分別下載；分開下載不再使用不存在的參數。
- 更新工具先下載、驗證，再替換；FFmpeg 兩個工具均驗證通過才安裝，替換失敗時回復已替換的檔案。
- 支援應用程式工具資料夾、系統 PATH 與自訂 FFmpeg／FFprobe 資料夾。
- 驗證網址、Windows 檔名及片段時間，下載大小依所選格式與片段長度估算。
- 支援播放清單與多個工作的序列佇列，完成後可開啟檔案／下載資料夾。
- 可展開、複製及儲存工作紀錄；記住下載資料夾、格式、工具位置與視窗大小。
- 視窗可縮放，支援 Windows 高 DPI，區分工作、完成、錯誤與取消狀態顏色。

## 使用方式

直接開啟 `dist\yt-dlp-downloader.exe`。EXE 已包含 Python 與 GUI 依賴；yt-dlp、FFmpeg 可透過程式按鈕安裝。

### 簡單模式

貼上網址，選下載位置及 MP4／MP3／M4A，按「下載影片」。

- MP4 只選 H.264／AAC 相容格式，再明確合併或轉封裝為 MP4。來源缺少此格式時會顯示錯誤，請使用進階模式選其他格式；不會偷偷退回其他容器。
- MP3／M4A 會提取或轉換音訊；簡單模式及片段下載需 FFmpeg 與 FFprobe。
- 「取得影片資訊／格式」可先取得影片資訊供大小估算；下載時不另外執行同步的大小查詢。

### 進階模式

取得格式後，選擇影片及／或音訊。

- 勾選合併：影音合併成一個檔案，需要 FFmpeg。
- 不勾選：以逗號格式選擇分別下載，檔名附上格式 ID，避免影音互相覆寫。
- 已含音訊的影片格式不可在合併模式另選音訊，避免所選音訊被忽略。
- 網址更改會清除舊選擇，或使用該網址已快取的格式資訊。

### 片段、播放清單與佇列

- 片段時間使用 `HH:MM:SS`，可附毫秒；結束留空下載到影片結尾。結束需大於開始，程式會先在背景取得資訊，當來源提供長度時檢查時間是否超出範圍。
- 精確到非關鍵影格的切點可能受原影片編碼限制；大小只提供粗估。
- 未勾選播放清單時最多下載單支影片。播放清單使用簡單模式，檔名包含順序與影片 ID；不支援播放清單片段或各片共用的進階格式 ID。
- 「加入佇列」保存當時的網址、路徑、格式及時間，按「開始佇列」逐一執行。單項失敗後繼續下一項並記錄錯誤。
- 取消佇列會停止目前項目，尚未開始的項目留在佇列；佇列不會保存到下次啟動。

### 工具與設定

工具與設定位於 `%APPDATA%\yt-dlp-gui`，設定檔為 `settings.ini`。

- yt-dlp 尋找順序：應用程式工具資料夾、EXE／原始碼旁的工具、系統 PATH。
- FFmpeg 尋找順序：自訂資料夾、應用程式工具資料夾、系統 PATH 上完整的工具組。
- 安裝／更新 FFmpeg 成功後會切換使用應用程式工具資料夾中的新版本。
- 網路或工具工作正在等待時，取消會待該步驟返回或逾時後完成；視窗仍可回應。
- 下載遇到錯誤可展開工作紀錄，查看退出碼、具體訊息與使用的工具路徑。

## 開發與打包

需要 Python 3.10 或以上：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -X utf8 -B test_update.py
.\.venv\Scripts\python.exe -X utf8 build.py
```

也可雙擊 `build.bat`；它會先切換到自己的資料夾，使用現有虛擬環境，不會偷偷安裝依賴。

實際 yt-dlp 的本機整合測試：

```powershell
$env:YT_DLP_TEST_EXE = (Resolve-Path .\yt-dlp.exe).Path
.\.venv\Scripts\python.exe -X utf8 -B test_integration.py
```

整合測試只連線至自己啟動的 localhost 測試伺服器；測試資料不是可播放的影片，目的是驗證 CLI 參數、資料傳輸、JSON 進度與檔名。網站端的限制、登入要求與實際影音內容仍需在來源網站測試。

## 原始碼結構

- `main.py`：GUI、設定及佇列管理。
- `downloader_core.py`：輸入驗證、工具定位、格式資訊與命令組合。
- `downloader_workers.py`：背景網路、下載、安裝、程序取消與安全替換。
- `style.py`：深色介面樣式。
- `test_update.py`：離線回歸測試。
- `test_integration.py`：實際 yt-dlp 的本機 HTTP 整合測試。
- `build.py`／`build.bat`：單檔 Windows EXE 打包。

問題回報：X（Twitter）@rj_sensei_。請附上工作紀錄中的錯誤訊息。

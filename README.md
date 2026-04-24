# Threads 貼文自動生成 AI Agent

為青椒家教經營 Threads 帳號，每日自動生成吸引國中家長的圖文貼文。

## 功能

- **內容生成**：輸入題目，AI（OpenRouter Claude Sonnet 4.6）生成完整貼文
- **圖文製作**：將文字疊加於背景圖（background 1 / 2 每日輪替）
- **短網址**：產生 LINE 短網址（reurl.cc），供置頂留言使用
- **本地輸出**：圖片輸出至 `output/` 資料夾

## 安裝

```bash
cd auto-post-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env，填入 OPENROUTER_API_KEY
```

## 使用

```bash
# 基本用法（需 OPENROUTER_API_KEY）
python main.py "假讀書"

# AI 自動產生題目（依日期、學期情境發想）
python main.py --auto-topic

# 使用範例內容測試（不需 API key）
python main.py "假讀書" --mock

# 指定開場風格
python main.py "孩子拖延怎麼辦" --style "情境描述"

# 指定輸出資料夾
python main.py "讀書方法" -o my_post

# 詳細輸出（DEBUG，用於除錯）
python main.py "假讀書" -v
```

## Web 介面（Apple 風格前端）

專案提供 Web 介面，整合所有功能於單一頁面。

### 啟動方式

```bash
# 終端 1：啟動後端 API
cd auto-post-agent
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# 終端 2：啟動前端
cd frontend
npm install
npm run dev
```

瀏覽器開啟 `http://localhost:5173` 即可使用。

### 功能

- 手動輸入題目或 AI 自動產生
- 可選開場風格（親子對話、痛點提問、情境描述等）
- Mock 模式（測試用，不需 API key）
- 一鍵複製貼文開頭與置頂留言
- 圖片預覽與下載全部

### 環境變數（前端）

| 變數 | 說明 |
|------|------|
| VITE_API_BASE | 後端 API 網址（預設空字串，開發時由 Vite proxy 轉發） |

## Docker

使用 Docker 一鍵啟動前後端，輸出目錄會掛載至本機 `output/`，生成的圖片可持久保存與下載。

```bash
# 建立 .env（若尚未建立）
cp .env.example .env
# 編輯 .env 填入 OPENROUTER_API_KEY、REURL_API_KEY 等

# 建置並啟動
docker compose up -d

# 瀏覽器開啟 http://localhost:8000
```

### 檔案下載

- **圖片預覽**：結果頁面可點擊圖片放大
- **下載全部**：點擊「下載全部」會下載 ZIP 檔（含該次生成的所有圖片）
- **輸出目錄**：`./output/` 會掛載至容器，生成的圖片同時存在本機，可直接從 `output/{timestamp}/` 存取

### 指令

```bash
docker compose up -d      # 背景啟動
docker compose down      # 停止
docker compose logs -f    # 查看日誌
```

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| OPENROUTER_API_KEY | 是 | OpenRouter API Key |
| REURL_API_KEY | 否 | reurl.cc 短網址（登入 [reurl.cc](https://reurl.cc/main/dev/doc) 取得 ApiKey；未設則使用原始 LINE URL） |
| THREADS_ACCESS_TOKEN | 否 | Threads 發文用（預留） |
| THREADS_USER_ID | 否 | Threads 用戶 ID（預留） |

## 輸出

- 圖片：`output/{timestamp}/slide_01.png` ~ `slide_N.png`
- 置頂留言文字：`免費一對一家教配對歡迎直接私訊或點擊連結加入官方 LINE：{short_url}`

## 背景圖

- `demo post/background 1.png`：綠漸層（奇數日使用）
- `demo post/background 2.png`：白→淺黃（偶數日使用）

## 每日排程（cron）

```bash
# 每天上午 9 點執行，AI 自動產生題目
0 9 * * * cd /path/to/auto-post-agent && .venv/bin/python main.py --auto-topic

# 或從檔案讀取題目（每行一題，取當日對應行）
0 9 * * * cd /path/to/auto-post-agent && .venv/bin/python main.py "$(sed -n $(date +\%u)p topics.txt)"
```

## 字體

專案內建 [LXGW WenKai TC](https://fonts.google.com/specimen/LXGW+WenKai+TC)（霞鶩文楷繁體）與 Noto Color Emoji，位於 `fonts/` 目錄。若字體遺失，請從 [Google Fonts](https://fonts.google.com/specimen/LXGW+WenKai+TC) 下載並放入 `fonts/`。Fallback：PingFang TC（macOS）、Noto Sans CJK（Linux）、微軟正黑體（Windows）。

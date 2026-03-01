# 部署指南：GitHub 上傳與 Hostinger VPS 部署

本文件提供將 auto-post-agent 專案上傳至 GitHub，以及部署到 Hostinger VPS 的完整步驟。

---

## 第一部分：上傳到 GitHub

### 步驟 1：確認 .env 不會被上傳（重要！）

專案中的 `.env` 含有 API 金鑰，**絕對不能**上傳到 GitHub。請確認 `.gitignore` 已包含：

```
.env
.env.*
!.env.example
```

### 步驟 2：初始化 Git 儲存庫

在專案根目錄執行：

```bash
cd /Users/wuyusen/Desktop/auto-post-agent
git init
```

### 步驟 3：建立 GitHub 遠端儲存庫

1. 登入 [GitHub](https://github.com)
2. 點擊右上角 **+** → **New repository**
3. 填寫：
   - **Repository name**：`auto-post-bot`（或自訂名稱）
   - **Description**：Threads 貼文自動生成 AI Agent
   - 選擇 **Private** 或 **Public**
   - **不要**勾選 "Add a README file"（專案已有）
4. 點擊 **Create repository**

### 步驟 4：加入檔案並推送

```bash
# 加入所有檔案（.gitignore 會自動排除 .env、node_modules 等）
git add .

# 檢查將要提交的檔案（確認沒有 .env）
git status

# 第一次提交
git commit -m "Initial commit: Threads 貼文自動生成 AI Agent"

# 將本地 main 分支連接到遠端（請將 YOUR_USERNAME 換成你的 GitHub 帳號）
git remote add origin https://github.com/eason034056/auto-post-bot.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

若使用 SSH：

```bash
git remote add origin git@github.com:eason034056/auto-post-bot.git
git push -u origin main
```

### 步驟 5：後續更新

之後若有修改，使用：

```bash
git add .
git commit -m "描述你的修改"
git push
```

---

## 第二部分：部署到 Hostinger VPS

### 前置需求

- Hostinger VPS 已購買並可 SSH 連線
- 有 VPS 的 IP 位址、SSH 使用者名稱與密碼（或 SSH key）

### 步驟 1：SSH 連線到 VPS

```bash
# 使用密碼登入（將 YOUR_IP 換成 VPS IP，root 可能是你的使用者名稱）
ssh root@YOUR_IP

# 或使用 SSH key
ssh -i ~/.ssh/your_key root@YOUR_IP
```

### 步驟 2：安裝必要軟體

在 VPS 上執行（以 Ubuntu/Debian 為例）：

```bash
# 更新系統
apt update && apt upgrade -y

# 安裝 Docker
curl -fsSL https://get.docker.com | sh

# 安裝 Docker Compose（若未隨 Docker 安裝）
apt install docker-compose-plugin -y

# 安裝 Git
apt install git -y

# 驗證安裝
docker --version
docker compose version
```

### 步驟 3：從 GitHub 克隆專案

```bash
# 建立工作目錄
mkdir -p /opt/apps
cd /opt/apps

# 克隆專案（公開 repo 直接 clone；私有 repo 需設定 SSH key 或 token）
git clone https://github.com/eason034056/auto-post-bot.git
cd auto-post-bot
```

**若為私有儲存庫**，可使用 Personal Access Token：

```bash
git clone https://YOUR_TOKEN@github.com/eason034056/auto-post-bot.git
```

或先在 VPS 上設定 SSH key，再使用 `git clone git@github.com:...`。

### 步驟 4：建立 .env 檔案

```bash
# 複製範例
cp .env.example .env

# 編輯 .env，填入你的 API 金鑰
nano .env
```

填入以下變數（至少 `OPENROUTER_API_KEY` 必填）：

```
OPENROUTER_API_KEY=sk-or-v1-你的金鑰
REURL_API_KEY=你的reurl金鑰（可選）
THREADS_ACCESS_TOKEN=
THREADS_USER_ID=
```

儲存：`Ctrl+O` → `Enter` → `Ctrl+X`

### 步驟 5：建置並啟動 Docker 容器

```bash
# 建置映像並啟動（首次會較久，需下載 base image 與 npm build）
docker compose up -d --build

# 查看容器狀態
docker compose ps

# 查看日誌（若有問題）
docker compose logs -f
```

### 步驟 6：設定防火牆（若 VPS 有啟用）

```bash
# 開放 8000 埠
ufw allow 8000
ufw enable
ufw status
```

### 步驟 7：驗證服務

在瀏覽器開啟：

```
http://YOUR_VPS_IP:8000
```

應可看到 Web 介面。

### 步驟 8：（可選）使用 Nginx 反向代理 + HTTPS

若希望使用網域與 HTTPS：

```bash
# 安裝 Nginx 與 Certbot
apt install nginx certbot python3-certbot-nginx -y

# 建立 Nginx 設定（將 your-domain.com 換成你的網域）
nano /etc/nginx/sites-available/auto-post-agent
```

內容：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

啟用並取得憑證：

```bash
ln -s /etc/nginx/sites-available/auto-post-agent /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
certbot --nginx -d your-domain.com
```

### 步驟 9：設定開機自動啟動

Docker Compose 的 `restart: unless-stopped` 已會讓容器在重啟後自動啟動。若需確保 Docker 服務本身開機啟動：

```bash
systemctl enable docker
```

### 常用指令

| 指令 | 說明 |
|------|------|
| `docker compose up -d` | 背景啟動 |
| `docker compose down` | 停止並移除容器 |
| `docker compose logs -f` | 即時查看日誌 |
| `docker compose pull && docker compose up -d --build` | 拉取最新程式碼後重新建置 |

### 更新部署（程式碼有變更時）

```bash
cd /opt/apps/auto-post-bot
git pull
docker compose up -d --build
```

---

## 疑難排解

### 1. 無法連線到 8000 埠

- 檢查防火牆：`ufw status`
- 檢查 Docker 容器：`docker compose ps`
- 檢查日誌：`docker compose logs -f`

### 2. 建置失敗

- 確認記憶體足夠（建議至少 2GB RAM）
- 檢查 `docker compose logs` 錯誤訊息
- 嘗試 `docker compose build --no-cache` 重新建置

### 3. API 金鑰錯誤

- 確認 `.env` 存在且格式正確
- 確認沒有多餘空格或引號
- 重啟容器：`docker compose restart`

### 4. 圖片無法下載

- 確認 `output/` 目錄已正確掛載：`docker compose` 中 `volumes: - ./output:/app/output`
- 檢查 VPS 磁碟空間：`df -h`

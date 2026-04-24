#!/usr/bin/env bash
# 從本機同步 secrets/sa.json 與 .env 到 Hostinger VPS。
#
# 這個腳本**只處理被 gitignore 的檔案**（git push 不會帶過去的那些），
# 不是完整部署 — code 更新請用 git push + VPS git pull。
#
# 用法：
#   ./scripts/deploy-secrets.sh           # 上傳 secrets/sa.json 與 .env
#   ./scripts/deploy-secrets.sh --verify  # 只檢查伺服器端檔案狀態

set -euo pipefail  # 💡 任一行失敗就中止，避免後續指令拿到壞狀態繼續跑

# ── 設定 ───────────────────────────────────────────────
# 💡 預設用 ~/.ssh/config 裡設好的 alias「auto-post-bot」
#    允許環境變數覆寫方便切 staging / prod：
#    e.g. SSH_TARGET=root@1.2.3.4 ./scripts/deploy-secrets.sh
SSH_TARGET="${SSH_TARGET:-auto-post-bot}"
REMOTE_DIR="${REMOTE_DIR:-/opt/apps/auto-post-bot}"

# ── 顏色輸出（純 UX，fail 時比較容易一眼看到） ────
G='\033[0;32m'  # green
R='\033[0;31m'  # red
Y='\033[0;33m'  # yellow
N='\033[0m'     # reset

log()  { echo -e "${G}✓${N} $1"; }
warn() { echo -e "${Y}!${N} $1"; }
fail() { echo -e "${R}✗${N} $1" >&2; exit 1; }

# ── --verify 模式：只讀遠端狀態，不上傳 ────────────
if [[ "${1:-}" == "--verify" ]]; then
  log "檢查遠端檔案狀態：$SSH_TARGET:$REMOTE_DIR"
  ssh "$SSH_TARGET" "ls -la $REMOTE_DIR/secrets/sa.json $REMOTE_DIR/.env 2>&1 || echo '(不存在)'"
  exit 0
fi

# ── 前置檢查：本機檔案存在？ ──────────────────────
[[ -f secrets/sa.json ]] || fail "本機 secrets/sa.json 不存在，是否搞錯目錄？"
[[ -f .env ]]            || fail "本機 .env 不存在"

log "本機檔案就緒，開始上傳到 $SSH_TARGET:$REMOTE_DIR"

# ── 1. 建目錄 ─────────────────────────────────────
ssh "$SSH_TARGET" "mkdir -p $REMOTE_DIR/secrets" \
  || fail "無法建立遠端目錄（SSH 連不上？）"
log "遠端目錄 OK"

# ── 2. SCP 上傳 ──────────────────────────────────
scp secrets/sa.json "$SSH_TARGET:$REMOTE_DIR/secrets/sa.json" \
  || fail "上傳 sa.json 失敗"
log "sa.json 已上傳"

scp .env "$SSH_TARGET:$REMOTE_DIR/.env" \
  || fail "上傳 .env 失敗"
log ".env 已上傳"

# ── 3. 鎖權限（安全邊界） ──────────────────────────
# ⚠️ 600 = 只有檔案擁有者可讀寫；700 = 其他人連 ls 目錄都不行
ssh "$SSH_TARGET" "
  chmod 600 $REMOTE_DIR/secrets/sa.json $REMOTE_DIR/.env
  chmod 700 $REMOTE_DIR/secrets
" || fail "chmod 失敗"
log "權限已鎖（secrets/sa.json=600, secrets/=700, .env=600）"

# ── 4. 最後驗證 ──────────────────────────────────
echo ""
warn "遠端檔案狀態："
ssh "$SSH_TARGET" "ls -la $REMOTE_DIR/secrets/sa.json $REMOTE_DIR/.env"

echo ""
log "全部完成！下一步：在 VPS 跑 'docker compose up -d' 或 'docker compose restart'"

"""Google Sheets 紀錄模組：pipeline 完成後寫一列貼文 metadata。

設計原則：
- **非阻塞**：Sheets 寫入失敗只 log warning，絕不讓 pipeline 崩潰
- **feature flag**：若未設定 GOOGLE_SHEETS_ID，整段邏輯靜默略過
- **自動建表頭**：第一次寫入時若試算表空，自動寫入欄位名稱那一列

認證：Service Account JSON（非 OAuth 使用者流）
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    GOOGLE_SHEETS_ID,
    GOOGLE_SHEETS_SA_JSON_PATH,
    GOOGLE_SHEETS_TAB_NAME,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

# 💡 欄位順序 = 試算表欄位順序。若要新增欄位，加在 metrics 之前以免破壞現有資料
COLUMNS = [
    "timestamp",
    "topic",
    "hook",
    "structure_name",
    "content_strategy",
    "opening_style",
    "research_used",
    "research_report",
    "slide_count",
    "slide_types",
    "discussion_question",
    "short_url",
    "pinned_comment_text",
    "output_dir",
    # ── 以下為 Stage 2 發文後回填欄位 ──
    "threads_post_id",
    "likes",
    "reposts",
    "replies",
    "views",
    "metrics_updated_at",
]


def _get_worksheet():
    """連線取得目標 worksheet。任何錯誤回傳 None 讓上層降級。"""
    # Lazy import：沒設 feature flag 時不強制要求 gspread 可用
    import gspread

    if not GOOGLE_SHEETS_SA_JSON_PATH:
        logger.warning("未設定 GOOGLE_SHEETS_SA_JSON_PATH，Sheets 功能停用")
        return None

    # 💡 相對路徑一律以 PROJECT_ROOT 為基底，不受 cwd 影響（容器內 cwd=/app 也能用）
    sa_path = Path(GOOGLE_SHEETS_SA_JSON_PATH).expanduser()
    if not sa_path.is_absolute():
        sa_path = PROJECT_ROOT / sa_path

    if not sa_path.exists():
        logger.warning("Service Account JSON 不存在：%s", sa_path)
        return None

    client = gspread.service_account(filename=str(sa_path))
    sheet = client.open_by_key(GOOGLE_SHEETS_ID)
    try:
        return sheet.worksheet(GOOGLE_SHEETS_TAB_NAME)
    except gspread.WorksheetNotFound:
        # ⚠️ fallback：若分頁名對不上，就用第一個分頁
        logger.warning("找不到分頁 %s，改用第一個分頁", GOOGLE_SHEETS_TAB_NAME)
        return sheet.sheet1


def _ensure_header(ws) -> None:
    """若試算表第一列空或不符，寫入欄位名稱。冪等操作。"""
    first_row = ws.row_values(1)
    if first_row == COLUMNS:
        return
    if not first_row:
        ws.update(range_name="A1", values=[COLUMNS])
        logger.info("Sheets 表頭已建立：%d 欄", len(COLUMNS))
    else:
        # 有表頭但與預期不符 — 不動它，讓使用者自己處理
        logger.warning("Sheets 表頭與預期不符（長度 %d vs %d），略過自動修正",
                       len(first_row), len(COLUMNS))


def _build_row(
    result: dict[str, Any],
    topic: str,
    opening_style: str | None,
) -> list[Any]:
    """依 COLUMNS 順序組合一列資料。單純資料轉換，不做 I/O。"""
    content = result.get("content", {})
    slides = content.get("slides", [])
    research_report = result.get("research_report")

    row_dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "hook": result.get("hook", ""),
        "structure_name": result.get("structure_name", ""),
        "content_strategy": " → ".join(result.get("content_strategy", [])),
        "opening_style": opening_style or "auto",
        "research_used": "YES" if research_report else "NO",
        "research_report": research_report or "",
        "slide_count": len(slides),
        "slide_types": ",".join(s.get("type", "") for s in slides),
        "discussion_question": result.get("discussion_question", ""),
        "short_url": result.get("short_url", ""),
        "pinned_comment_text": result.get("pinned_comment_text", ""),
        "output_dir": str(result.get("output_dir", "")),
        "threads_post_id": "",
        "likes": "",
        "reposts": "",
        "replies": "",
        "views": "",
        "metrics_updated_at": "",
    }
    return [row_dict.get(col, "") for col in COLUMNS]


def _write_row_strict(
    result: dict[str, Any],
    topic: str,
    opening_style: str | None,
) -> None:
    """嚴格模式：任何錯誤都 raise。供前端按鈕路徑使用（要顯示錯誤給使用者）。"""
    if not GOOGLE_SHEETS_ID:
        raise RuntimeError("未設定 GOOGLE_SHEETS_ID，無法寫入 Sheets")

    ws = _get_worksheet()
    if ws is None:
        raise RuntimeError("Service Account 未設定或 JSON 無效")

    _ensure_header(ws)
    ws.append_row(_build_row(result, topic, opening_style), value_input_option="USER_ENTERED")


def log_from_metadata(subdir: str) -> dict[str, Any]:
    """讀 output/{subdir}/_metadata.json 寫進 Sheets。

    回傳：{success: bool, message: str, already_logged?: bool}
    ⚠️ 本函式不 raise — 前端依 success 欄位判斷狀態。
    """
    meta_path = OUTPUT_DIR / subdir / "_metadata.json"
    if not meta_path.exists():
        return {"success": False, "message": f"找不到 metadata 檔：{meta_path.name}"}

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"success": False, "message": f"metadata 格式錯誤：{e}"}

    if meta.get("logged_to_sheets"):
        return {
            "success": True,
            "already_logged": True,
            "message": "這份內容已經記錄過了",
        }

    # 重建成 _write_row_strict 需要的 result 結構
    result = {
        "content": {"slides": meta.get("slides", [])},
        "hook": meta.get("hook", ""),
        "structure_name": meta.get("structure_name", ""),
        "content_strategy": meta.get("content_strategy", []),
        "discussion_question": meta.get("discussion_question", ""),
        "short_url": meta.get("short_url", ""),
        "pinned_comment_text": meta.get("pinned_comment_text", ""),
        "output_dir": meta.get("output_dir", ""),
        "research_report": meta.get("research_report"),
    }

    try:
        _write_row_strict(result, topic=meta.get("topic", ""), opening_style=meta.get("opening_style"))
    except Exception as e:
        logger.warning("Sheets 寫入失敗：%s", e)
        return {"success": False, "message": f"寫入失敗：{e}"}

    # 標記已記錄，下次點同一張不會重複寫
    meta["logged_to_sheets"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"success": True, "already_logged": False, "message": "已記錄到 Google Sheets"}

"""Short URL service using reurl.cc API."""
import json
import logging
import re

import requests

from .config import LINE_URL, REURL_API_KEY

logger = logging.getLogger(__name__)

# reurl.cc 官方 API：https://reurl.cc/main/dev/doc (需登入查看)
# 常見回傳非 JSON 原因：錯誤 endpoint、過期 key、回傳 HTML 錯誤頁
REURL_API_URL = "https://api.reurl.cc/shorten"


def _safe_json(resp: requests.Response) -> dict | None:
    """安全解析 JSON，失敗時記錄回應內容供除錯。"""
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        preview = (resp.text or "")[:300].replace("\n", " ")
        logger.debug(
            "reurl.cc 回傳非 JSON：status=%d, content_type=%s, body_preview=%s",
            resp.status_code,
            resp.headers.get("Content-Type", ""),
            preview,
        )
        logger.warning(
            "短網址 API 回傳無法解析的內容（非 JSON）：%s。請確認 REURL_API_KEY 正確且未過期。",
            str(e),
        )
        return None


def shorten_url(long_url: str = LINE_URL, api_key: str | None = None) -> str:
    """
    Shorten URL using reurl.cc API.

    Args:
        long_url: URL to shorten (default: LINE URL)
        api_key: reurl.cc API key (default: from env REURL_API_KEY)

    Returns:
        Short URL, or original URL if API fails or no key
    """
    key = api_key or REURL_API_KEY
    if not key:
        logger.info("未設定 REURL_API_KEY，使用原始 URL")
        return long_url

    logger.info("產生短網址：%s", long_url[:50] + "..." if len(long_url) > 50 else long_url)

    try:
        # reurl.cc 官方 API 格式（依文件）：POST + url + ApiKey header
        resp = requests.post(
            REURL_API_URL,
            json={"url": long_url},
            headers={"reurl-api-key": key},
            timeout=10,
        )
        data = _safe_json(resp)
        if data:
            # 可能的回傳欄位：short_url, url, short
            result = data.get("short_url") or data.get("url") or data.get("short")
            if result:
                logger.info("短網址產生成功：%s", result)
                return result

        # 若回傳非 JSON，嘗試從 body 提取 reurl.cc 格式短網址
        if resp.text and "reurl.cc" in resp.text:
            match = re.search(r"https?://reurl\.cc/[^\s\"'<>]+", resp.text)
            if match:
                logger.info("從回應中解析短網址：%s", match.group(0))
                return match.group(0)
    except requests.RequestException as e:
        logger.warning("短網址 API 請求失敗：%s，使用原始 URL", e)

    logger.info("使用原始 URL")
    return long_url


def get_pinned_comment_text(short_url: str) -> str:
    """Format the pinned comment text with CTA and short URL."""
    return f"免費一對一家教配對歡迎點擊連結或QR Code加入官方 LINE：{short_url}"

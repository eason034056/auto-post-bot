"""HTML-based image renderer — Playwright + Jinja2 替代 PIL 程式化繪圖。

設計理念（對比舊的 image_generator.py）：
- 宣告式渲染：描述「長什麼樣」，而非「怎麼畫」
- CSS 武器庫：陰影、漸層、字距、hairline、layout 皆為一等公民
- 視覺升級：極簡高級風（米白底 + 近黑字 + 品牌色 hairline）

Phase 1 範圍：只支援 slide.type="title"，其他類型尚未實作。
"""
from __future__ import annotations

import atexit
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import Browser, Playwright, sync_playwright

from .config import FONTS_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)

IMG_W, IMG_H = 1080, 1350

TEMPLATE_DIR = Path(__file__).parent / "html_templates"

# 相容舊版：保留 emoji 替換（某些 emoji Noto Sans 沒有字形）
EMOJI_REPLACEMENTS: dict[str, str] = {
    "❌": "×", "✘": "×", "✗": "×",
    "🎯": "★", "🎓": "◆", "👉": "▶", "➤": "▶", "➜": "→",
}


# ── Jinja2 環境（模組載入時建立一次） ────────────────────────────

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ── Browser singleton（跨 slide 重用，大幅提升效能） ────────────
# 💡 Playwright 啟動成本高（~1 秒），10 張 slide 重用同一個 browser
#    能把總時間從 ~10s 壓到 ~2s

_playwright: Playwright | None = None
_browser: Browser | None = None


def _get_browser() -> Browser:
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch()
        logger.debug("Playwright Chromium started")
    return _browser


def _close_browser() -> None:
    global _playwright, _browser
    if _browser is not None:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright is not None:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None


# ⚠️ 註冊 atexit 避免程式結束時殘留 Chromium 子進程
atexit.register(_close_browser)


# ── slide dict 預處理 ─────────────────────────────────────────

def _replace_emoji(text: str) -> str:
    for emoji, replacement in EMOJI_REPLACEMENTS.items():
        text = text.replace(emoji, replacement)
    return text


def _sanitize(value: Any) -> Any:
    """遞迴把 slide dict 裡的字串做 emoji 替換。"""
    if isinstance(value, str):
        return _replace_emoji(value)
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    return value


_TITLE_EYEBROW_FALLBACK = "觀點 / INSIGHT"


def _prepare_title_context(slide: dict) -> dict:
    """title：根據 content 行數切換版型
    - 1 行 → is_short（真金句 pull-quote，accent hairline 上下夾）
    - 2+ 行 → is_long（最後一行當副標，主標走 editorial 左對齊）
    - tag 沒給 → fallback 為「觀點 / INSIGHT」確保 eyebrow 一定出現

    💡 之前把 2 行也判 short 是錯的：AI 在 prompt 指引下會產「主標+副標」
       兩行，當 pull-quote 放會造成 104px 字+長句導致孤字換行。
    """
    content = slide.get("content", "")
    lines = [ln for ln in content.split("\n") if ln.strip()]
    is_short = len(lines) <= 1

    ctx = {
        "is_short": is_short,
        "eyebrow": slide.get("tag") or _TITLE_EYEBROW_FALLBACK,
    }
    if is_short:
        ctx["title_lines"] = lines
        ctx["subtitle_lines"] = []
    else:
        ctx["title_lines"] = lines[:-1]
        ctx["subtitle_lines"] = [lines[-1]]
    return ctx


def _prepare_numbered_context(slide: dict) -> dict:
    """numbered：剝掉 example 前的「例如：」前綴。"""
    example = slide.get("example", "")
    if example:
        example = example.lstrip().lstrip("例如：").lstrip("例如:").strip()
    return {"example": example}


def _prepare_case_study_context(slide: dict) -> dict:
    """case_study：把 problem / solution / result 合併成 sections 列表。

    💡 用 sections 統一模板對三段的處理，AI 漏掉其中一段也不會破版。
    """
    sections = []
    mapping = [("problem", "問題"), ("solution", "方法"), ("result", "結果")]
    for key, label in mapping:
        val = slide.get(key)
        if not val:
            continue
        if isinstance(val, list):
            val = "\n".join(f"・{v}" for v in val)
        sections.append({"label": label, "content": str(val)})

    # fallback：三段都沒給，就用 content 做單段
    if not sections and slide.get("content"):
        sections.append({"label": "內容", "content": str(slide["content"])})

    return {"sections": sections}


def _prepare_summary_context(slide: dict) -> dict:
    """summary：第 1-2 行做大引言，其餘做補充 body。"""
    content = slide.get("content", "")
    lines = [ln for ln in content.split("\n") if ln.strip()]
    if len(lines) >= 3:
        return {"quote_text": "\n".join(lines[:2]), "quote_body": "\n".join(lines[2:])}
    return {"quote_text": "\n".join(lines), "quote_body": ""}


def _prepare_data_context(slide: dict) -> dict:
    """data：正規化 stats 為 list。
    - 支援單欄位 `stat` + `label`（舊格式相容）
    - 支援 `stats: [{value, label}, ...]`（推薦格式）
    - 1 個 stat → is_single（巨大置中）；2+ stats → is_multi（橫列 grid）
    """
    stats = slide.get("stats") or []
    # 舊格式 fallback：單一 stat/value + label
    if not stats:
        value = slide.get("stat") or slide.get("value")
        label = slide.get("label", "")
        if value:
            stats = [{"value": value, "label": label}]
    return {"stats": stats, "is_single": len(stats) == 1}


def _prepare_comparison_context(slide: dict) -> dict:
    """comparison：正規化 rows 為 [{left, right}, ...]。
    rows 若為空則給預設 rows=[]，模板會只顯示 header。
    """
    rows = slide.get("rows") or []
    # 標準化：支援 dict / 兩元素 list
    normalized = []
    for r in rows:
        if isinstance(r, dict):
            normalized.append({"left": r.get("left", ""), "right": r.get("right", "")})
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            normalized.append({"left": str(r[0]), "right": str(r[1])})
    return {"rows": normalized}


_CONTEXT_PREP = {
    "title": _prepare_title_context,
    "bullet_list": lambda s: {},  # 直接用 slide dict 的 title/items/footer
    "numbered": _prepare_numbered_context,
    "case_study": _prepare_case_study_context,
    "summary": _prepare_summary_context,
    "data": _prepare_data_context,
    "comparison": _prepare_comparison_context,
    "cta": lambda s: {},  # 固定內容，template 自己填
}


# ── 渲染核心 ─────────────────────────────────────────────────

def _render_html_string(slide: dict, index: int, total: int) -> str:
    """把 slide dict 渲染成完整 HTML 字串。"""
    slide_type = slide.get("type", "title")
    prep = _CONTEXT_PREP.get(slide_type)
    if prep is None:
        raise NotImplementedError(
            f"slide type '{slide_type}' not supported by HTML renderer"
        )
    extra_ctx = prep(slide)

    # ⚠️ 先合併再 spread — 避免 slide 與 extra_ctx 同鍵（如 example）撞 TypeError
    ctx = {**slide, **extra_ctx}
    template = _env.get_template(f"{slide_type}.html.j2")
    return template.render(
        **ctx,
        index=index + 1,  # 外部顯示 1-based
        total=total,
        fonts_dir=str(FONTS_DIR),
    )


def render_slide(slide: dict, index: int, total: int, output_path: Path) -> None:
    """渲染單張 slide 成 PNG。

    流程：
    1. Jinja2 模板 + slide dict → HTML 字串
    2. HTML 字串寫到 output_path 同目錄的 _html/ 子目錄（方便 debug）
    3. Playwright goto file:// 該 HTML → 截圖為 PNG
    """
    slide = _sanitize(slide)
    html = _render_html_string(slide, index, total)

    # 寫 HTML 到實體檔（file:// 字型載入需要 file origin）
    html_dir = output_path.parent / "_html"
    html_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / f"{output_path.stem}.html"
    html_path.write_text(html, encoding="utf-8")

    browser = _get_browser()
    page = browser.new_page(viewport={"width": IMG_W, "height": IMG_H})
    try:
        # 💡 wait_until="networkidle" 確保 @font-face 載入完成才截圖
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.screenshot(path=str(output_path), omit_background=False, full_page=False)
    finally:
        page.close()


def generate_images(content: dict, output_subdir: str | None = None) -> list[Path]:
    """產生所有 slide 圖片（對外契約與舊 image_generator.generate_images 一致）。"""
    if output_subdir:
        out_dir = OUTPUT_DIR / output_subdir
    else:
        out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    slides = content.get("slides", [])
    total = len(slides)

    try:
        for i, slide in enumerate(slides):
            out_path = out_dir / f"slide_{i + 1:02d}.png"
            logger.info("  slide_%02d.png (type=%s)", i + 1, slide.get("type"))
            render_slide(slide, i, total, out_path)
            paths.append(out_path)
    finally:
        # Phase 1：跑完就關，避免 dev 反覆跑時 Chromium 累積
        _close_browser()

    logger.info("HTML 圖片產生完成：%d 張 → %s", len(paths), out_dir)
    return paths

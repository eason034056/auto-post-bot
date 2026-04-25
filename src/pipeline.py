"""Main pipeline: topic -> (research) -> content -> images -> short URL.

提供兩種介面：
- run_pipeline_streaming(): generator，逐階段 yield 進度事件，給 SSE 端點 / 前端進度條使用
- run_pipeline():            阻塞版，內部其實是 streaming 版的 drain wrapper（向下相容 CLI 與舊 API）
"""
import json
import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR
from .content_generator import generate_content
from .html_image_generator import _close_browser, render_slide
from .researcher import is_research_available, run_research
from .short_url import get_pinned_comment_text, shorten_url

logger = logging.getLogger(__name__)


def _save_metadata(
    output_dir: Path,
    result: dict,
    topic: str,
    style_hint: str | None,
) -> None:
    """存 _metadata.json 供之後使用者手動觸發 Sheets 紀錄用。

    💡 存在本地而非當場寫 Sheets，讓「生成 → 要不要記錄」變成兩個獨立動作，
       配合使用者真實工作流（並非每篇都發、常會重生）。
    """
    meta = {
        "topic": topic,
        "opening_style": style_hint or "auto",
        "hook": result.get("hook", ""),
        "structure_name": result.get("structure_name", ""),
        "content_strategy": result.get("content_strategy", []),
        "discussion_question": result.get("discussion_question", ""),
        "short_url": result.get("short_url", ""),
        "pinned_comment_text": result.get("pinned_comment_text", ""),
        "research_report": result.get("research_report"),
        "slides": result.get("content", {}).get("slides", []),
        "output_dir": str(result.get("output_dir", "")),
        "logged_to_sheets": False,  # 由 /api/log-to-sheets 成功後改成 True
    }
    meta_path = output_dir / "_metadata.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("metadata 已存：%s", meta_path)


# ── Streaming generator（SSE 端點主邏輯） ─────────────────────


def run_pipeline_streaming(
    topic: str,
    output_subdir: str | None = None,
    style_hint: str | None = None,
    research: bool = False,
) -> Iterator[dict[str, Any]]:
    """逐階段 yield 進度事件的 pipeline 版本。

    事件格式：
        {"type": "progress", "phase": str, "step": int, "total": int, "message": str,
         "sub_current": int?, "sub_total": int?}     # progress 事件
        {"type": "complete", "result": dict}          # 最終結果（與 run_pipeline 回傳同形）
        {"type": "error", "detail": str}              # 任何階段失敗

    💡 圖片階段用「手動 iterate slides」實作 sub-progress（每張圖 yield 一次），
       而不是包裝 generate_images 的 callback —— callback 改成 yield 需要 thread+queue
       橋接，過於複雜；inline iterate 反而最直接。
    """
    try:
        # 計算總階段數（research 是 optional）
        will_research = research and is_research_available()
        total_phases = 4 if will_research else 3
        current_step = 0

        logger.info("Streaming pipeline 啟動：題目=%s, 深度研究=%s", topic, "啟用" if will_research else "停用")

        # === Phase: Research（可選）===
        research_report: str | None = None
        if research and not is_research_available():
            logger.warning("研究功能不可用（OPENROUTER_API_KEY 未設定），跳過深度研究")

        if will_research:
            current_step += 1
            yield {
                "type": "progress",
                "phase": "research",
                "step": current_step,
                "total": total_phases,
                "message": "深度研究中（Perplexity 多輪搜尋，約 3-5 分鐘）...",
            }
            research_report = run_research(topic)
            yield {
                "type": "progress",
                "phase": "research_done",
                "step": current_step,
                "total": total_phases,
                "message": (
                    f"研究完成（{len(research_report)} 字）"
                    if research_report
                    else "研究失敗，將使用純 AI 撰寫"
                ),
            }

        # === Phase: Content ===
        current_step += 1
        yield {
            "type": "progress",
            "phase": "content",
            "step": current_step,
            "total": total_phases,
            "message": "產生貼文內容（Claude Sonnet）...",
        }
        content = generate_content(
            topic, style_hint=style_hint, research_context=research_report
        )
        slides = content.get("slides", [])
        yield {
            "type": "progress",
            "phase": "content_done",
            "step": current_step,
            "total": total_phases,
            "message": f"內容產生完成（{len(slides)} 張投影片）",
        }

        # === Phase: Images（含 sub-progress）===
        current_step += 1
        subdir = output_subdir or datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = OUTPUT_DIR / subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        slides_total = len(slides)
        image_paths: list[Path] = []

        yield {
            "type": "progress",
            "phase": "images",
            "step": current_step,
            "total": total_phases,
            "sub_current": 0,
            "sub_total": slides_total,
            "message": f"產生圖片 0/{slides_total}（Playwright 啟動中）...",
        }

        try:
            for i, slide in enumerate(slides):
                out_path = out_dir / f"slide_{i + 1:02d}.png"
                render_slide(slide, i, slides_total, out_path)
                image_paths.append(out_path)
                yield {
                    "type": "progress",
                    "phase": "images",
                    "step": current_step,
                    "total": total_phases,
                    "sub_current": i + 1,
                    "sub_total": slides_total,
                    "message": f"產生圖片 {i + 1}/{slides_total}（{slide.get('type', '')}）",
                }
        finally:
            # ⚠️ 一定要關 browser，避免 Chromium 子進程殘留
            _close_browser()

        # === Phase: Short URL ===
        current_step += 1
        yield {
            "type": "progress",
            "phase": "short_url",
            "step": current_step,
            "total": total_phases,
            "message": "產生置頂留言短網址...",
        }
        short_url = shorten_url()
        pinned_text = get_pinned_comment_text(short_url)

        # === 組裝結果 + 寫 metadata ===
        result: dict[str, Any] = {
            "content": content,
            "hook": content.get("hook", ""),
            "structure_name": content.get("structure_name", ""),
            "content_strategy": content.get("content_strategy", []),
            "discussion_question": content.get("discussion_question", ""),
            "image_paths": image_paths,
            "short_url": short_url,
            "pinned_comment_text": pinned_text,
            "output_dir": OUTPUT_DIR / subdir,
            "research_report": research_report,
        }
        _save_metadata(OUTPUT_DIR / subdir, result, topic, style_hint)

        logger.info("Streaming pipeline 完成")
        yield {"type": "complete", "result": result}

    except Exception as e:  # noqa: BLE001 — 任何階段失敗都要轉成 error 事件
        logger.exception("Streaming pipeline 失敗")
        yield {"type": "error", "detail": str(e)}


# ── 阻塞版（向下相容）──────────────────────────────────────────


def run_pipeline(
    topic: str,
    output_subdir: str | None = None,
    style_hint: str | None = None,
    research: bool = False,
) -> dict:
    """阻塞版 pipeline：drain streaming generator，回傳最終 result。

    💡 為什麼這樣寫：CLI 與舊的 /api/generate 不需要進度，但邏輯應該與
    streaming 版完全一致 —— 用 drain 模式自動繼承所有改動，不會雙軌維護。
    """
    final_result: dict | None = None
    error_detail: str | None = None

    for event in run_pipeline_streaming(
        topic,
        output_subdir=output_subdir,
        style_hint=style_hint,
        research=research,
    ):
        if event.get("type") == "complete":
            final_result = event["result"]
        elif event.get("type") == "error":
            error_detail = event.get("detail", "unknown error")

    if error_detail:
        raise RuntimeError(f"Pipeline 失敗：{error_detail}")
    if final_result is None:
        raise RuntimeError("Pipeline 未回傳 complete 事件（不應發生）")
    return final_result

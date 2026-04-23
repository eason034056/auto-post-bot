"""Main pipeline: topic -> (research) -> content -> images -> short URL."""
import json
import logging
from datetime import datetime
from pathlib import Path

from .config import OUTPUT_DIR
from .content_generator import generate_content
from .html_image_generator import generate_images
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


def run_pipeline(
    topic: str,
    output_subdir: str | None = None,
    style_hint: str | None = None,
    research: bool = False,
) -> dict:
    """
    Run full pipeline: (optional research) -> generate content -> images -> short URL.

    Args:
        topic: Post topic (e.g. "假讀書")
        output_subdir: Optional output folder name
        style_hint: Optional opening style override
        research: If True, run Perplexity deep research before content generation

    Returns:
        Dict with: content, image_paths, short_url, pinned_comment_text, research_report
    """
    logger.info("開始 pipeline：題目=%s, 深度研究=%s", topic, "啟用" if research else "停用")

    # 0. Deep research (optional)
    research_report = None
    if research:
        if is_research_available():
            total_steps = 4
            logger.info("步驟 1/%d：Perplexity 深度研究...", total_steps)
            research_report = run_research(topic)
            if research_report:
                logger.info("深度研究完成，報告 %d 字", len(research_report))
            else:
                logger.warning("深度研究失敗，將使用純 AI 產生內容")
        else:
            total_steps = 3
            logger.warning("研究功能不可用（OPENROUTER_API_KEY 未設定），跳過深度研究")
    else:
        total_steps = 3

    # 1. Generate content (with research context if available)
    step = 2 if research else 1
    logger.info("步驟 %d/%d：產生貼文內容...", step, total_steps)
    content = generate_content(topic, style_hint=style_hint, research_context=research_report)

    # 2. Generate images
    subdir = output_subdir or datetime.now().strftime("%Y%m%d_%H%M%S")
    step += 1
    logger.info("步驟 %d/%d：產生圖片（輸出至 %s）...", step, total_steps, subdir)
    image_paths = generate_images(content, output_subdir=subdir)

    # 3. Short URL for pinned comment
    step += 1
    logger.info("步驟 %d/%d：產生短網址...", step, total_steps)
    short_url = shorten_url()
    pinned_text = get_pinned_comment_text(short_url)

    result = {
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

    # 4. 存 metadata（不直接寫 Sheets — 由使用者後續手動觸發）
    _save_metadata(OUTPUT_DIR / subdir, result, topic, style_hint)

    logger.info("Pipeline 完成")
    return result

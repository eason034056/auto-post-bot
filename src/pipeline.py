"""Main pipeline: topic -> content -> images -> short URL."""
import logging
from datetime import datetime
from pathlib import Path

from .config import OUTPUT_DIR
from .content_generator import generate_content
from .image_generator import generate_images
from .short_url import get_pinned_comment_text, shorten_url

logger = logging.getLogger(__name__)


def run_pipeline(
    topic: str,
    output_subdir: str | None = None,
    style_hint: str | None = None,
) -> dict:
    """
    Run full pipeline: generate content, images, and short URL.

    Args:
        topic: Post topic (e.g. "假讀書")
        output_subdir: Optional output folder name
        style_hint: Optional opening style override

    Returns:
        Dict with: content, image_paths, short_url, pinned_comment_text
    """
    logger.info("開始 pipeline：題目=%s", topic)

    # 1. Generate content
    logger.info("步驟 1/3：產生貼文內容...")
    content = generate_content(topic, style_hint=style_hint)

    # 2. Generate images
    subdir = output_subdir or datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info("步驟 2/3：產生圖片（輸出至 %s）...", subdir)
    image_paths = generate_images(content, output_subdir=subdir)

    # 3. Short URL for pinned comment
    logger.info("步驟 3/3：產生短網址...")
    short_url = shorten_url()
    pinned_text = get_pinned_comment_text(short_url)

    logger.info("Pipeline 完成")

    return {
        "content": content,
        "hook": content.get("hook", ""),
        "image_paths": image_paths,
        "short_url": short_url,
        "pinned_comment_text": pinned_text,
        "output_dir": OUTPUT_DIR / subdir,
    }

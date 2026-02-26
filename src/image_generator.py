"""Image generation: overlay text on background images using Pillow."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import BACKGROUND_1, BACKGROUND_2, FONTS_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)


# LXGW WenKai TC 霞鶩文楷（繁體）— 專案內建字體
LXGW_REGULAR = FONTS_DIR / "LXGWWenKaiTC-Regular.ttf"
LXGW_BOLD = FONTS_DIR / "LXGWWenKaiTC-Bold.ttf"

# 若模型仍輸出 emoji，替換為字型可渲染的符號（安全網）
EMOJI_REPLACEMENTS: dict[str, str] = {
    "❌": "×", "✘": "×", "✗": "×",
    "🎯": "★", "🎓": "◆", "👉": "▶", "➤": "▶", "➜": "→",
}


def _replace_emoji(text: str) -> str:
    """將 emoji 替換為字型可渲染的符號（模型已禁止 emoji，此為安全網）。"""
    for emoji, replacement in EMOJI_REPLACEMENTS.items():
        text = text.replace(emoji, replacement)
    return text


def _get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """載入 LXGW WenKai TC，支援 regular / bold 粗細。"""
    path = LXGW_BOLD if weight == "bold" and LXGW_BOLD.exists() else LXGW_REGULAR
    if path.exists():
        logger.debug("載入字型：%s, size=%d, weight=%s", path.name, size, weight)
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    for p, idx in [
        ("/System/Library/Fonts/PingFang.ttc", 1),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("C:/Windows/Fonts/msjh.ttc", 0),
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size, index=idx)
            except OSError:
                continue
    return ImageFont.load_default()


def _get_background_path() -> Path:
    """Alternate background by day: odd day -> bg1, even day -> bg2.
    Docker 請設定 TZ (e.g. America/Chicago) 以依當地日期切換。"""
    day = datetime.now().day
    return BACKGROUND_1 if day % 2 == 1 else BACKGROUND_2


def _get_text_color(background_path: Path) -> tuple[int, int, int]:
    """White for green bg (bg1), dark for light bg (bg2)."""
    if "background 1" in str(background_path):
        return (255, 255, 255)  # white on green
    return (50, 50, 50)  # dark on white/yellow


# 換行時預留邊距，避免字型渲染造成右側切字
WRAP_SAFETY = 20


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text to fit max_width, returns list of lines."""
    effective_width = max(100, max_width - WRAP_SAFETY)
    lines = []
    for paragraph in text.split("\n"):
        words = list(paragraph)
        current = ""
        for char in words:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= effective_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def _draw_title_slide(img: Image.Image, draw: ImageDraw.ImageDraw, content: str, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw title/hook slide - 大標粗體、置中。"""
    w, h = img.size
    margin = 80
    max_width = w - margin * 2
    title_font = _get_font(52, "bold")
    lines = _wrap_text(draw, content, title_font, max_width)

    total_height = sum(draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] for line in lines)
    line_height = int(total_height / len(lines)) + 24 if lines else 48
    start_y = (h - total_height - (len(lines) - 1) * 24) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        y = start_y + i * line_height
        draw.text((x, y), line, font=title_font, fill=color)


def _draw_bullet_list(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw bullet list - 標題粗體大、項目中、footer 小，長文自動換行，整體上下置中。"""
    w, h = img.size
    margin = 80
    max_width = w - margin * 2
    x = margin

    title_font = _get_font(50, "bold")
    item_font = _get_font(34)
    footer_font = _get_font(28)

    # 先計算總高度
    total_h = 0
    if slide.get("title"):
        for line in _wrap_text(draw, _replace_emoji(slide["title"]), title_font, max_width):
            total_h += draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] + 8
        total_h += 20
    for item in slide.get("items", []):
        for line in _wrap_text(draw, _replace_emoji("• " + item), item_font, max_width):
            total_h += draw.textbbox((0, 0), line, font=item_font)[3] - draw.textbbox((0, 0), line, font=item_font)[1] + 22
    if slide.get("footer"):
        total_h += 18
        for line in _wrap_text(draw, _replace_emoji(slide["footer"]), footer_font, max_width):
            total_h += draw.textbbox((0, 0), line, font=footer_font)[3] - draw.textbbox((0, 0), line, font=footer_font)[1] + 12

    y = (h - total_h) // 2

    if slide.get("title"):
        for line in _wrap_text(draw, _replace_emoji(slide["title"]), title_font, max_width):
            draw.text((x, y), line, font=title_font, fill=color)
            bbox = draw.textbbox((0, 0), line, font=title_font)
            y += bbox[3] - bbox[1] + 8
        y += 20

    for item in slide.get("items", []):
        for line in _wrap_text(draw, _replace_emoji("• " + item), item_font, max_width):
            draw.text((x, y), line, font=item_font, fill=color)
            bbox = draw.textbbox((0, 0), line, font=item_font)
            y += bbox[3] - bbox[1] + 22

    if slide.get("footer"):
        y += 18
        for line in _wrap_text(draw, _replace_emoji(slide["footer"]), footer_font, max_width):
            draw.text((x, y), line, font=footer_font, fill=color)
            bbox = draw.textbbox((0, 0), line, font=footer_font)
            y += bbox[3] - bbox[1] + 12


def _draw_numbered_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw numbered method - 編號與標題粗體、內文與例如較小，長文自動換行，整體上下置中。"""
    w, h = img.size
    margin = 80
    max_width = w - margin * 2
    x = margin

    num_font = _get_font(46, "bold")
    title_font = _get_font(40, "bold")
    content_font = _get_font(32)
    example_font = _get_font(28)

    num = slide.get("number", 1)
    title = slide.get("title", "")
    header = f'{num}.【{title}】'

    # 先計算總高度
    total_h = draw.textbbox((0, 0), header, font=num_font)[3] - draw.textbbox((0, 0), header, font=num_font)[1] + 72
    content = slide.get("content", "")
    for paragraph in content.split("\n"):
        for line in _wrap_text(draw, _replace_emoji(paragraph), content_font, max_width):
            total_h += draw.textbbox((0, 0), line, font=content_font)[3] - draw.textbbox((0, 0), line, font=content_font)[1] + 14
    example_text = ""
    if slide.get("example"):
        #  strip 開頭「例如：」避免與下方繪製的標籤重複
        example_text = slide["example"].lstrip().lstrip("例如：").lstrip("例如:").strip()
        total_h += 18 + (draw.textbbox((0, 0), "例如:", font=example_font)[3] - draw.textbbox((0, 0), "例如:", font=example_font)[1]) + 38
        for paragraph in example_text.split("\n"):
            for line in _wrap_text(draw, _replace_emoji(paragraph), example_font, max_width):
                total_h += draw.textbbox((0, 0), line, font=example_font)[3] - draw.textbbox((0, 0), line, font=example_font)[1] + 10

    y = (h - total_h) // 2

    draw.text((x, y), header, font=num_font, fill=color)
    y += 72

    for paragraph in content.split("\n"):
        for line in _wrap_text(draw, _replace_emoji(paragraph), content_font, max_width):
            draw.text((x, y), line, font=content_font, fill=color)
            bbox = draw.textbbox((0, 0), line, font=content_font)
            y += bbox[3] - bbox[1] + 14

    if example_text:
        y += 18
        draw.text((x, y), "例如:", font=example_font, fill=color)
        y += 38
        for paragraph in example_text.split("\n"):
            for line in _wrap_text(draw, _replace_emoji(paragraph), example_font, max_width):
                draw.text((x, y), line, font=example_font, fill=color)
                bbox = draw.textbbox((0, 0), line, font=example_font)
                y += bbox[3] - bbox[1] + 10


def _draw_case_study_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw case study - 標題粗體大、內文較小，長文自動換行，整體上下置中。"""
    w, h = img.size
    margin = 80
    max_width = w - margin * 2
    x = margin

    title_font = _get_font(46, "bold")
    body_font = _get_font(32)

    def _calc_case_study_height() -> int:
        th = 0
        if slide.get("title"):
            for line in _wrap_text(draw, _replace_emoji("• " + slide["title"]), title_font, max_width):
                th += draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] + 8
            th += 20
        for key in ("problem", "solution", "result"):
            val = slide.get(key)
            if val:
                if isinstance(val, list):
                    val = "\n".join(f"- {v}" for v in val)
                for paragraph in str(val).split("\n"):
                    for line in _wrap_text(draw, "  " + paragraph.strip(), body_font, max_width):
                        th += draw.textbbox((0, 0), line, font=body_font)[3] - draw.textbbox((0, 0), line, font=body_font)[1] + 12
                th += 15
        if not any(slide.get(k) for k in ("problem", "solution", "result")) and slide.get("content"):
            for paragraph in str(slide["content"]).split("\n"):
                for line in _wrap_text(draw, _replace_emoji(paragraph), body_font, max_width):
                    th += draw.textbbox((0, 0), line, font=body_font)[3] - draw.textbbox((0, 0), line, font=body_font)[1] + 12
        return th

    y = (h - _calc_case_study_height()) // 2

    if slide.get("title"):
        for line in _wrap_text(draw, _replace_emoji("• " + slide["title"]), title_font, max_width):
            draw.text((x, y), line, font=title_font, fill=color)
            bbox = draw.textbbox((0, 0), line, font=title_font)
            y += bbox[3] - bbox[1] + 8
        y += 20

    for key, label in [("problem", "問題"), ("solution", "調整方法"), ("result", "結果")]:
        val = slide.get(key)
        if val:
            if isinstance(val, list):
                val = "\n".join(f"- {v}" for v in val)
            for paragraph in str(val).split("\n"):
                for line in _wrap_text(draw, "  " + paragraph.strip(), body_font, max_width):
                    draw.text((x, y), line, font=body_font, fill=color)
                    bbox = draw.textbbox((0, 0), line, font=body_font)
                    y += bbox[3] - bbox[1] + 12
            y += 15

    if not any(slide.get(k) for k in ("problem", "solution", "result")) and slide.get("content"):
        for paragraph in str(slide["content"]).split("\n"):
            for line in _wrap_text(draw, _replace_emoji(paragraph), body_font, max_width):
                draw.text((x, y), line, font=body_font, fill=color)
                bbox = draw.textbbox((0, 0), line, font=body_font)
                y += bbox[3] - bbox[1] + 12


def _draw_summary_slide(img: Image.Image, draw: ImageDraw.ImageDraw, content: str, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw summary - 金句粗體、置中。"""
    w, h = img.size
    margin = 80
    summary_font = _get_font(44, "bold")
    lines = _wrap_text(draw, content, summary_font, w - margin * 2)
    line_height = 54
    start_y = (h - len(lines) * line_height) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=summary_font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, start_y + i * line_height), _replace_emoji(line), font=summary_font, fill=color)


def _draw_cta_slide(img: Image.Image, draw: ImageDraw.ImageDraw, content: str, font: ImageFont.FreeTypeFont, color: tuple) -> None:
    """Draw CTA - 標題粗體大、內文較小，長文自動換行，整體上下置中。"""
    w, h = img.size
    margin = 80
    max_width = w - margin * 2
    x = margin

    title_font = _get_font(46, "bold")
    body_font = _get_font(34)

    # 先計算總高度
    total_h = 0
    for i, raw_line in enumerate(content.split("\n")):
        f = title_font if i == 0 else body_font
        prefix = "• " if i == 0 else "→ " if "點擊" in raw_line or "Line" in raw_line else ""
        text = _replace_emoji(prefix + raw_line)
        for line in _wrap_text(draw, text, f, max_width):
            total_h += draw.textbbox((0, 0), line, font=f)[3] - draw.textbbox((0, 0), line, font=f)[1] + 24

    y = (h - total_h) // 2

    for i, raw_line in enumerate(content.split("\n")):
        f = title_font if i == 0 else body_font
        prefix = "• " if i == 0 else "→ " if "點擊" in raw_line or "Line" in raw_line else ""
        text = _replace_emoji(prefix + raw_line)
        for line in _wrap_text(draw, text, f, max_width):
            draw.text((x, y), line, font=f, fill=color)
            bbox = draw.textbbox((0, 0), line, font=f)
            y += bbox[3] - bbox[1] + 24


def _sanitize_slide(slide: dict[str, Any]) -> dict[str, Any]:
    """對 slide 所有文字欄位執行 emoji 替換。"""
    sanitized = {}
    for k, v in slide.items():
        if isinstance(v, str):
            sanitized[k] = _replace_emoji(v)
        elif isinstance(v, list):
            sanitized[k] = [_replace_emoji(i) if isinstance(i, str) else i for i in v]
        else:
            sanitized[k] = v
    return sanitized


def render_slide(slide: dict[str, Any], background_path: Path, output_path: Path, text_color: tuple) -> None:
    """Render a single slide to output_path."""
    slide = _sanitize_slide(slide)
    img = Image.open(background_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _get_font(40)

    slide_type = slide.get("type", "title")
    if slide_type == "title":
        _draw_title_slide(img, draw, slide.get("content", ""), font, text_color)
    elif slide_type == "bullet_list":
        _draw_bullet_list(img, draw, slide, font, text_color)
    elif slide_type == "numbered":
        _draw_numbered_slide(img, draw, slide, font, text_color)
    elif slide_type == "case_study":
        _draw_case_study_slide(img, draw, slide, font, text_color)
    elif slide_type == "summary":
        _draw_summary_slide(img, draw, slide.get("content", ""), font, text_color)
    elif slide_type == "cta":
        _draw_cta_slide(img, draw, slide.get("content", ""), font, text_color)
    else:
        _draw_title_slide(img, draw, slide.get("content", str(slide)), font, text_color)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")


def generate_images(content: dict[str, Any], output_subdir: str | None = None) -> list[Path]:
    """
    Generate all slide images from content.

    Args:
        content: Dict with "slides" array from content_generator
        output_subdir: Optional subdir under output/ (e.g. timestamp)

    Returns:
        List of output file paths
    """
    background_path = _get_background_path()
    text_color = _get_text_color(background_path)
    logger.info("背景圖：%s", background_path.name)

    if output_subdir:
        out_dir = OUTPUT_DIR / output_subdir
    else:
        from datetime import datetime
        out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    slides = content.get("slides", [])

    for i, slide in enumerate(slides):
        out_path = out_dir / f"slide_{i + 1:02d}.png"
        slide_type = slide.get("type", "title")
        logger.info("  產生 slide_%02d.png (type=%s)", i + 1, slide_type)
        render_slide(slide, background_path, out_path, text_color)
        paths.append(out_path)

    logger.info("圖片產生完成：%d 張 → %s", len(paths), out_dir)
    return paths

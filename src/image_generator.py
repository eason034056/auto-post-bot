"""Image generation — 全新設計系統，參考 @fishtvlove carousel 風格。

不再依賴外部背景圖片，改為程式化繪製：
- 深色 / 淺色 / 品牌色三種背景交替
- 膠囊標籤、圓形編號徽章、裝飾條、圓角卡片等設計元素
- 品牌綠色系 (#427A5B) 作為主色調
"""
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import FONTS_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)

# ── 尺寸 ──────────────────────────────────────────────────────

IMG_W, IMG_H = 1080, 1350  # 4:5 比例（Instagram / Threads 標準）
MARGIN = 80                 # 左右邊距

# ── 品牌色系（來自青椒老師 tailwind brand palette）──────────

BRAND_500 = (66, 122, 91)    # #427A5B  主色
BRAND_400 = (130, 176, 97)   # #82b061  亮綠（深色背景強調）
BRAND_200 = (180, 205, 147)  # #B4CD93  淺綠
BRAND_100 = (216, 235, 200)  # #d8ebc8
BRAND_50  = (240, 247, 237)  # #f0f7ed  極淺綠

# 深色背景 & 文字色
DARK_BG    = (30, 41, 59)     # #1e293b  neutral-800
LIGHT_BG   = BRAND_50         # #f0f7ed
ACCENT_BG  = BRAND_500        # #427A5B  全屏主色

# 漸層色對（top → bottom，營造深度感）
DARK_GRAD   = ((22, 30, 45), (38, 50, 68))
LIGHT_GRAD  = ((250, 248, 242), (236, 241, 230))
ACCENT_GRAD = ((56, 110, 80), (76, 135, 100))

WHITE      = (255, 255, 255)
TEXT_DARK  = (30, 41, 59)     # #1e293b
TEXT_MUTED_ON_DARK  = (148, 163, 184)  # #94a3b8  neutral-400
TEXT_MUTED_ON_LIGHT = (100, 116, 139)  # #64748b  neutral-500
CARD_BG_ON_LIGHT    = (226, 232, 224)  # 淺灰綠卡片底色
CARD_BG_WARM        = (232, 213, 196)  # 暖色卡片（用於對比 "現在" 側）

# ── 字型（Noto Sans CJK TC — 粗黑體 sans-serif）─────────────

NOTO_REGULAR = FONTS_DIR / "NotoSansCJKtc-Regular.otf"
NOTO_BOLD    = FONTS_DIR / "NotoSansCJKtc-Bold.otf"
NOTO_BLACK   = FONTS_DIR / "NotoSansCJKtc-Black.otf"

# 舊字型保留作為 fallback
_LXGW_REGULAR = FONTS_DIR / "LXGWWenKaiTC-Regular.ttf"
_LXGW_BOLD    = FONTS_DIR / "LXGWWenKaiTC-Bold.ttf"

EMOJI_REPLACEMENTS: dict[str, str] = {
    "❌": "×", "✘": "×", "✗": "×",
    "🎯": "★", "🎓": "◆", "👉": "▶", "➤": "▶", "➜": "→",
}


def _replace_emoji(text: str) -> str:
    for emoji, replacement in EMOJI_REPLACEMENTS.items():
        text = text.replace(emoji, replacement)
    return text


def _get_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """載入 Noto Sans CJK TC 字型。

    weight 支援三種：
    - "regular": Regular（內文）
    - "bold": Bold（標題、強調）
    - "black": Black（封面大標題，最粗）
    """
    # 優先使用 Noto Sans CJK TC
    font_map = {
        "black": NOTO_BLACK,
        "bold": NOTO_BOLD,
        "regular": NOTO_REGULAR,
    }
    path = font_map.get(weight, NOTO_REGULAR)
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass

    # Fallback: LXGW WenKai TC
    fallback = _LXGW_BOLD if weight in ("bold", "black") and _LXGW_BOLD.exists() else _LXGW_REGULAR
    if fallback.exists():
        try:
            return ImageFont.truetype(str(fallback), size)
        except OSError:
            pass

    # System fallback
    for p, idx in [
        ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("C:/Windows/Fonts/msjh.ttc", 0),
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size, index=idx)
            except OSError:
                continue
    return ImageFont.load_default()


# ── 文字工具 ──────────────────────────────────────────────────

WRAP_SAFETY = 20


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    effective_width = max(100, max_width - WRAP_SAFETY)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
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


def _text_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


# ── 背景主題 ──────────────────────────────────────────────────

def _get_slide_theme(slide_type: str, index: int, total: int) -> str:
    """根據 slide type 決定背景主題。

    mapping 設計：
    - title (封面)     → dark
    - bullet_list      → light
    - numbered         → dark
    - case_study       → light
    - summary (金句)   → accent（品牌色全屏）
    - cta (結尾)       → dark
    """
    if slide_type == "title":
        return "dark"
    if slide_type == "cta":
        return "dark"
    if slide_type == "summary":
        return "accent"
    if slide_type == "bullet_list":
        return "light"
    if slide_type == "numbered":
        return "dark"
    if slide_type == "case_study":
        return "light"
    # fallback：依奇偶交替
    return "dark" if index % 2 == 0 else "light"


def _draw_gradient(img: Image.Image, color_top: tuple, color_bottom: tuple) -> None:
    """繪製垂直線性漸層背景。"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for i in range(h):
        ratio = i / h
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, i), (w, i)], fill=(r, g, b))


def _apply_noise(img: Image.Image, intensity: int = 12) -> None:
    """加上微噪點紋理，營造類底片質感。

    💡 在 1/4 解析度生成噪點再放大，效能比逐像素快 ~16 倍，
    且放大的模糊效果反而更自然。
    """
    small_w, small_h = img.size[0] // 4, img.size[1] // 4
    noise = Image.new("L", (small_w, small_h))
    noise_pixels = noise.load()
    for ny in range(small_h):
        for nx in range(small_w):
            noise_pixels[nx, ny] = 128 + random.randint(-intensity, intensity)
    noise = noise.resize(img.size, Image.BILINEAR)
    noise_rgb = Image.merge("RGB", [noise, noise, noise])
    blended = Image.blend(img, noise_rgb, 0.06)
    img.paste(blended)


def _draw_decorations(img: Image.Image, draw: ImageDraw.ImageDraw, theme: str) -> None:
    """加上微妙的幾何裝飾元素，增加視覺層次。"""
    if theme == "dark":
        # 右上角大半透明圓
        circle_color = (38, 52, 72)
        r = 280
        draw.ellipse([IMG_W - r + 80, -r + 80, IMG_W + r + 80, r + 80], fill=circle_color)
        # 左下角小裝飾圓
        draw.ellipse([- 60, IMG_H - 180, 120, IMG_H - 0], fill=(35, 48, 66))
    elif theme == "light":
        # 右下角柔和大圓
        circle_color = (228, 236, 218)
        r = 320
        draw.ellipse([IMG_W - r + 60, IMG_H - r + 60, IMG_W + r + 60, IMG_H + r + 60],
                     fill=circle_color)
    elif theme == "accent":
        # 右上角稍亮圓
        circle_color = (80, 145, 110)
        r = 250
        draw.ellipse([IMG_W - r + 100, -r + 100, IMG_W + r + 100, r + 100],
                     fill=circle_color)


def _create_canvas(theme: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    grad = {"dark": DARK_GRAD, "light": LIGHT_GRAD, "accent": ACCENT_GRAD}[theme]
    img = Image.new("RGB", (IMG_W, IMG_H), grad[0])
    _draw_gradient(img, grad[0], grad[1])
    _apply_noise(img)
    draw = ImageDraw.Draw(img)
    _draw_decorations(img, draw, theme)
    return img, draw


def _theme_colors(theme: str) -> dict:
    """回傳該主題下的各角色顏色。"""
    if theme == "dark":
        return {
            "title": WHITE,
            "body": (210, 218, 226),        # 稍暗白
            "muted": TEXT_MUTED_ON_DARK,
            "accent": BRAND_400,             # 亮綠（在深色背景上更易讀）
            "badge_bg": BRAND_500,
            "badge_text": WHITE,
            "label": BRAND_400,
            "card_bg": (41, 55, 76),         # 比背景稍亮的卡片
            "card_border": BRAND_500,
        }
    if theme == "accent":
        return {
            "title": WHITE,
            "body": (220, 235, 220),
            "muted": (190, 215, 195),
            "accent": WHITE,
            "badge_bg": WHITE,
            "badge_text": BRAND_500,
            "label": WHITE,
            "card_bg": (55, 105, 78),        # 比主色稍暗
            "card_border": WHITE,
        }
    # light
    return {
        "title": TEXT_DARK,
        "body": (51, 65, 85),                # neutral-700
        "muted": TEXT_MUTED_ON_LIGHT,
        "accent": BRAND_500,
        "badge_bg": BRAND_500,
        "badge_text": WHITE,
        "label": BRAND_500,
        "card_bg": CARD_BG_ON_LIGHT,
        "card_border": BRAND_200,
    }


# ── 裝飾元素繪製 ──────────────────────────────────────────────

def _draw_pill_badge(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                     bg_color: tuple, text_color: tuple, font: ImageFont.FreeTypeFont) -> int:
    """繪製膠囊形標籤，回傳高度（含下方間距）。"""
    tw = _text_width(draw, text, font)
    th = _text_height(draw, text, font)
    pad_x, pad_y = 24, 12
    pill_w = tw + pad_x * 2
    pill_h = th + pad_y * 2
    draw.rounded_rectangle(
        [x, y, x + pill_w, y + pill_h],
        radius=pill_h // 2,
        fill=bg_color,
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=text_color)
    return pill_h + 24


def _draw_circle_badge(draw: ImageDraw.ImageDraw, number: int, cx: int, cy: int,
                       radius: int, bg_color: tuple, text_color: tuple, font: ImageFont.FreeTypeFont) -> None:
    """繪製圓形編號徽章。"""
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=bg_color,
    )
    num_str = str(number)
    # 💡 anchor="mm" 讓 PIL 以 (cx, cy) 為中心自動對齊，避免手動計算 bbox 偏移
    draw.text((cx, cy), num_str, font=font, fill=text_color, anchor="mm")


def _draw_rounded_square_badge(draw: ImageDraw.ImageDraw, number: int, x: int, y: int,
                               size: int, bg_color: tuple, text_color: tuple,
                               font: ImageFont.FreeTypeFont) -> None:
    """繪製圓角方形編號徽章。"""
    draw.rounded_rectangle(
        [x, y, x + size, y + size],
        radius=size // 4,
        fill=bg_color,
    )
    num_str = str(number)
    draw.text((x + size // 2, y + size // 2), num_str, font=font, fill=text_color, anchor="mm")


def _draw_decorative_bar(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple) -> int:
    """繪製短裝飾橫條，回傳高度（含下方間距）。"""
    bar_w, bar_h = 60, 6
    draw.rounded_rectangle(
        [x, y, x + bar_w, y + bar_h],
        radius=bar_h // 2,
        fill=color,
    )
    return bar_h + 30


def _draw_section_label(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                        color: tuple) -> int:
    """繪製段落小標籤（如「從前的狀態」「核心差異」），回傳高度含間距。"""
    font = _get_font(32, "bold")
    draw.text((x, y), text, font=font, fill=color)
    return _text_height(draw, text, font) + 18


# ── Slide 繪製函式 ────────────────────────────────────────────

def _draw_title_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """封面頁：深色背景 + 膠囊標籤 + 大標題 + 副標題，整體垂直置中。

    參考圖 1/7：標籤 + 粗體白字標題 + 灰色副標
    """
    content = _replace_emoji(slide.get("content", ""))
    lines = content.split("\n")
    max_w = IMG_W - MARGIN * 2

    # 拆分：前幾行為標題，最後一行若較短可當副標題
    if len(lines) >= 3:
        title_lines = lines[:-1]
        subtitle_lines = lines[-1:]
    else:
        title_lines = lines
        subtitle_lines = []

    tag_text = slide.get("tag", "")
    tag_font = _get_font(30, "bold")
    title_font = _get_font(68, "black")
    sub_font = _get_font(36)

    # 先算總高度
    total_h = 0
    if tag_text:
        total_h += _text_height(draw, tag_text, tag_font) + 24 + 24  # pill height + gap
    for line in title_lines:
        for wl in _wrap_text(draw, line, title_font, max_w):
            total_h += _text_height(draw, wl, title_font) + 20
    if subtitle_lines:
        total_h += 20
        for line in subtitle_lines:
            for wl in _wrap_text(draw, line, sub_font, max_w):
                total_h += _text_height(draw, wl, sub_font) + 12

    y = (IMG_H - total_h) // 2

    # 膠囊標籤
    if tag_text:
        pill_h = _draw_pill_badge(draw, tag_text, MARGIN, y, colors["badge_bg"], colors["badge_text"], tag_font)
        y += pill_h

    # 大標題
    for line in title_lines:
        for wl in _wrap_text(draw, line, title_font, max_w):
            draw.text((MARGIN, y), wl, font=title_font, fill=colors["title"])
            y += _text_height(draw, wl, title_font) + 20

    # 副標題
    if subtitle_lines:
        y += 20
        for line in subtitle_lines:
            for wl in _wrap_text(draw, line, sub_font, max_w):
                draw.text((MARGIN, y), wl, font=sub_font, fill=colors["muted"])
                y += _text_height(draw, wl, sub_font) + 12


def _draw_bullet_list_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """列表頁：淺色背景 + 大標題 + 圓形編號項目 + footer。

    參考圖 2/7：粗體標題 + 圓形 badge 編號列表
    """
    max_w = IMG_W - MARGIN * 2
    items = slide.get("items", [])
    title_text = _replace_emoji(slide.get("title", ""))

    title_font = _get_font(56, "black")
    item_font = _get_font(36)
    badge_font = _get_font(30, "bold")
    footer_font = _get_font(30)
    badge_radius = 28
    badge_item_gap = 20
    item_x = MARGIN + badge_radius * 2 + badge_item_gap
    item_max_w = IMG_W - item_x - MARGIN

    # 計算總高度
    total_h = 0
    if title_text:
        for wl in _wrap_text(draw, title_text, title_font, max_w):
            total_h += _text_height(draw, wl, title_font) + 12
        total_h += 36  # 標題下間距

    for item in items:
        wrapped = _wrap_text(draw, _replace_emoji(item), item_font, item_max_w)
        line_block_h = sum(_text_height(draw, wl, item_font) + 8 for wl in wrapped)
        total_h += max(badge_radius * 2, line_block_h) + 28

    # 💡 footer 要過 _wrap_text，且高度要逐行累加，不然會超寬被裁掉
    footer_text = _replace_emoji(slide["footer"]) if slide.get("footer") else ""
    footer_lines = _wrap_text(draw, footer_text, footer_font, max_w) if footer_text else []
    if footer_lines:
        total_h += 28
        for fl in footer_lines:
            total_h += _text_height(draw, fl, footer_font) + 8

    y = (IMG_H - total_h) // 2

    # 大標題
    if title_text:
        for wl in _wrap_text(draw, title_text, title_font, max_w):
            draw.text((MARGIN, y), wl, font=title_font, fill=colors["title"])
            y += _text_height(draw, wl, title_font) + 12
        y += 36

    # 圓形編號項目
    for idx, item in enumerate(items, 1):
        wrapped = _wrap_text(draw, _replace_emoji(item), item_font, item_max_w)
        first_line_h = _text_height(draw, wrapped[0], item_font) if wrapped else 30
        badge_cy = y + first_line_h // 2

        _draw_circle_badge(draw, idx, MARGIN + badge_radius, badge_cy,
                           badge_radius, colors["badge_bg"], colors["badge_text"], badge_font)

        for wl in wrapped:
            draw.text((item_x, y), wl, font=item_font, fill=colors["body"])
            y += _text_height(draw, wl, item_font) + 8
        y += 20

    # footer（逐行繪製，與 total_h 計算對齊）
    if footer_lines:
        y += 8
        for fl in footer_lines:
            draw.text((MARGIN, y), fl, font=footer_font, fill=colors["muted"])
            y += _text_height(draw, fl, footer_font) + 8


def _draw_numbered_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """編號方法頁：深色背景 + 圓角方形 badge + 標題 + 說明 + 例如，垂直置中。

    參考圖 5/7：方形 badge + 粗體標題 + 說明文字 + 例如
    """
    max_w = IMG_W - MARGIN * 2
    num = slide.get("number", 1)
    title = _replace_emoji(slide.get("title", ""))
    content = _replace_emoji(slide.get("content", ""))
    example = slide.get("example", "")
    if example:
        example = _replace_emoji(example.lstrip().lstrip("例如：").lstrip("例如:").strip())

    badge_size = 60
    badge_font = _get_font(30, "bold")
    title_font = _get_font(52, "black")
    content_font = _get_font(36)
    example_font = _get_font(32)

    title_x = MARGIN + badge_size + 20
    title_max_w = max_w - badge_size - 20
    title_wrapped = _wrap_text(draw, title, title_font, title_max_w)

    # 計算總高度
    total_h = 0
    header_h = max(badge_size, sum(_text_height(draw, wl, title_font) + 8 for wl in title_wrapped))
    total_h += header_h + 30

    for paragraph in content.split("\n"):
        for wl in _wrap_text(draw, paragraph, content_font, max_w):
            total_h += _text_height(draw, wl, content_font) + 14

    if example:
        total_h += 24 + _text_height(draw, "例如:", example_font) + 14
        for paragraph in example.split("\n"):
            for wl in _wrap_text(draw, paragraph, example_font, max_w):
                total_h += _text_height(draw, wl, example_font) + 10

    y = (IMG_H - total_h) // 2

    # 方形 badge + 標題
    _draw_rounded_square_badge(draw, num, MARGIN, y, badge_size,
                               colors["badge_bg"], colors["badge_text"], badge_font)

    first_th = _text_height(draw, title_wrapped[0], title_font) if title_wrapped else badge_size
    ty = y + (badge_size - first_th) // 2
    for wl in title_wrapped:
        draw.text((title_x, ty), wl, font=title_font, fill=colors["title"])
        ty += _text_height(draw, wl, title_font) + 8

    y += header_h + 30

    # 內容
    for paragraph in content.split("\n"):
        for wl in _wrap_text(draw, paragraph, content_font, max_w):
            draw.text((MARGIN, y), wl, font=content_font, fill=colors["body"])
            y += _text_height(draw, wl, content_font) + 14

    # 例如
    if example:
        y += 12
        draw.text((MARGIN, y), "例如:", font=example_font, fill=colors["muted"])
        y += _text_height(draw, "例如:", example_font) + 14
        for paragraph in example.split("\n"):
            for wl in _wrap_text(draw, paragraph, example_font, max_w):
                draw.text((MARGIN + 16, y), wl, font=example_font, fill=colors["muted"])
                y += _text_height(draw, wl, example_font) + 10


def _draw_case_study_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """案例頁：淺色背景 + 段落標籤 + 標題 + 圓角卡片（左邊accent邊線）。

    參考圖 6/7：section label + 大標題 + 堆疊卡片（每張有 accent 左邊線 + 標題 + 內容）
    """
    max_w = IMG_W - MARGIN * 2
    title = _replace_emoji(slide.get("title", ""))
    title_font = _get_font(52, "black")
    label_font = _get_font(32, "bold")
    card_title_font = _get_font(36, "bold")
    card_body_font = _get_font(32)

    # 收集卡片資料
    cards = []
    for key, label in [("problem", "問題"), ("solution", "調整方法"), ("result", "結果")]:
        val = slide.get(key)
        if val:
            if isinstance(val, list):
                val = "\n".join(f"- {v}" for v in val)
            cards.append({"label": label, "content": _replace_emoji(str(val))})

    # 如果沒有 problem/solution/result，用 content 做單張卡片
    if not cards and slide.get("content"):
        cards.append({"label": "", "content": _replace_emoji(str(slide["content"]))})

    # 計算總高度
    card_pad = 24
    card_border_w = 5
    card_content_x = MARGIN + card_border_w + card_pad + 8
    card_max_w = IMG_W - card_content_x - MARGIN - card_pad

    # 💡 section label 是固定 tag「實際案例」，不是 AI 回傳的 title。
    #    原版拿 title 同字串畫兩次（小+大）會造成視覺重複；固定 tag 能兼顧類別辨識與層次感。
    section_label = "實際案例"

    total_h = 0
    if title:
        total_h += _text_height(draw, section_label, label_font) + 16
        for wl in _wrap_text(draw, title, title_font, max_w):
            total_h += _text_height(draw, wl, title_font) + 10
        total_h += 30

    for card in cards:
        card_h = card_pad * 2
        if card["label"]:
            card_h += _text_height(draw, card["label"], card_title_font) + 12
        for paragraph in card["content"].split("\n"):
            for wl in _wrap_text(draw, paragraph, card_body_font, card_max_w):
                card_h += _text_height(draw, wl, card_body_font) + 8
        card["height"] = card_h
        total_h += card_h + 16  # 卡片間距

    y = max(160, (IMG_H - total_h) // 2)

    # 段落標籤（固定 tag） + 大標題（AI 的 title）
    if title:
        draw.text((MARGIN, y), section_label, font=label_font, fill=colors["label"])
        y += _text_height(draw, section_label, label_font) + 16

        for wl in _wrap_text(draw, title, title_font, max_w):
            draw.text((MARGIN, y), wl, font=title_font, fill=colors["title"])
            y += _text_height(draw, wl, title_font) + 10
        y += 30

    # 卡片
    for card in cards:
        card_h = card["height"]
        card_x = MARGIN
        card_w = IMG_W - MARGIN * 2

        # 卡片陰影（偏移 4px，增加立體感）
        shadow_color = (max(0, colors["card_bg"][0] - 25),
                        max(0, colors["card_bg"][1] - 25),
                        max(0, colors["card_bg"][2] - 25))
        draw.rounded_rectangle(
            [card_x + 3, y + 4, card_x + card_w + 3, y + card_h + 4],
            radius=16,
            fill=shadow_color,
        )
        # 卡片底色（圓角矩形）
        draw.rounded_rectangle(
            [card_x, y, card_x + card_w, y + card_h],
            radius=16,
            fill=colors["card_bg"],
        )
        # 左邊 accent 邊線
        draw.rounded_rectangle(
            [card_x, y + 8, card_x + card_border_w, y + card_h - 8],
            radius=card_border_w // 2,
            fill=colors["card_border"],
        )

        cy = y + card_pad
        if card["label"]:
            draw.text((card_content_x, cy), card["label"], font=card_title_font, fill=colors["accent"])
            cy += _text_height(draw, card["label"], card_title_font) + 12

        for paragraph in card["content"].split("\n"):
            for wl in _wrap_text(draw, paragraph, card_body_font, card_max_w):
                draw.text((card_content_x, cy), wl, font=card_body_font, fill=colors["body"])
                cy += _text_height(draw, wl, card_body_font) + 8

        y += card_h + 16


def _draw_summary_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """金句頁：品牌色全屏 + 裝飾短條 + 大標題 + 左邊線引言。

    參考圖 3/7：accent 全屏背景 + 白色裝飾條 + 白色大標 + 白色段落（帶左邊線）
    """
    content = _replace_emoji(slide.get("content", ""))
    lines = content.split("\n")
    max_w = IMG_W - MARGIN * 2

    # 前兩行做大標題，其餘做引言
    if len(lines) >= 3:
        title_lines = lines[:2]
        body_lines = lines[2:]
    else:
        title_lines = lines
        body_lines = []

    title_font = _get_font(64, "black")
    body_font = _get_font(36)

    # 計算高度
    total_h = 36  # 裝飾條
    for line in title_lines:
        for wl in _wrap_text(draw, line, title_font, max_w):
            total_h += _text_height(draw, wl, title_font) + 16
    if body_lines:
        total_h += 30  # 間距
        for line in body_lines:
            for wl in _wrap_text(draw, line, body_font, max_w - 24):  # 留左邊線空間
                total_h += _text_height(draw, wl, body_font) + 12

    y = (IMG_H - total_h) // 2

    # 裝飾短條
    y += _draw_decorative_bar(draw, MARGIN, y, colors["accent"])

    # 大標題
    for line in title_lines:
        for wl in _wrap_text(draw, line, title_font, max_w):
            draw.text((MARGIN, y), wl, font=title_font, fill=colors["title"])
            y += _text_height(draw, wl, title_font) + 16

    # 引言段落（帶左邊線）
    if body_lines:
        y += 14
        body_x = MARGIN + 24  # 留左邊線空間
        body_start_y = y
        for line in body_lines:
            for wl in _wrap_text(draw, line, body_font, max_w - 24):
                draw.text((body_x, y), wl, font=body_font, fill=colors["body"])
                y += _text_height(draw, wl, body_font) + 12
            y += 8  # 段落間距

        # 左邊裝飾線
        line_x = MARGIN + 6
        draw.rounded_rectangle(
            [line_x, body_start_y, line_x + 4, y - 8],
            radius=2,
            fill=(*colors["accent"][:3], 180) if len(colors["accent"]) == 3 else colors["accent"],
        )


def _draw_cta_slide(img: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, colors: dict) -> None:
    """CTA 結尾頁：固定內容，不受 AI 生成影響。

    深色背景 + 置中大標題 + 副標 + accent 膠囊按鈕 + 追蹤提示
    """
    # ⚠️ CTA 頁使用固定內容，確保品牌一致性
    title_text = "青椒老師專業家教服務"
    body_lines = ["服務地區: 新竹 | 台北", "專業領域: 國高中小家教媒合"]
    cta_text = "點擊留言連結直接加入官方Line好友"
    follow_text = "追蹤青椒老師看更多學習方法"

    title_font = _get_font(56, "black")
    body_font = _get_font(34)
    cta_font = _get_font(34, "bold")
    follow_font = _get_font(28)
    max_w = IMG_W - MARGIN * 2

    # 計算總高度
    total_h = 0
    title_wrapped = _wrap_text(draw, title_text, title_font, max_w)
    for wl in title_wrapped:
        total_h += _text_height(draw, wl, title_font) + 14
    total_h += 30  # 標題下間距

    for line in body_lines:
        for wl in _wrap_text(draw, line, body_font, max_w):
            total_h += _text_height(draw, wl, body_font) + 10
    total_h += 40  # body 下間距

    # CTA 按鈕高度
    btn_pad_x, btn_pad_y = 48, 20
    max_btn_content_w = max_w - btn_pad_x * 2
    cta_wrapped = _wrap_text(draw, cta_text, cta_font, max_btn_content_w)
    cta_line_heights = [_text_height(draw, wl, cta_font) for wl in cta_wrapped]
    cta_line_spacing = 8
    total_btn_text_h = sum(cta_line_heights) + cta_line_spacing * (len(cta_wrapped) - 1)
    btn_h = total_btn_text_h + btn_pad_y * 2
    total_h += btn_h + 40

    total_h += 30 + 24  # 追蹤提示

    y = max(200, (IMG_H - total_h) // 2)

    # 置中大標題
    for wl in title_wrapped:
        tw = _text_width(draw, wl, title_font)
        draw.text(((IMG_W - tw) // 2, y), wl, font=title_font, fill=colors["title"])
        y += _text_height(draw, wl, title_font) + 14
    y += 30

    # 置中副標（服務資訊）
    for line in body_lines:
        for wl in _wrap_text(draw, line, body_font, max_w):
            tw = _text_width(draw, wl, body_font)
            draw.text(((IMG_W - tw) // 2, y), wl, font=body_font, fill=colors["muted"])
            y += _text_height(draw, wl, body_font) + 10
    y += 40

    # 膠囊 CTA 按鈕（文字用 anchor="mm" 垂直置中）
    max_line_w = max(_text_width(draw, wl, cta_font) for wl in cta_wrapped)
    btn_w = max_line_w + btn_pad_x * 2
    btn_x = (IMG_W - btn_w) // 2
    btn_radius = btn_h // 2 if len(cta_wrapped) == 1 else 24
    draw.rounded_rectangle(
        [btn_x, y, btn_x + btn_w, y + btn_h],
        radius=btn_radius,
        fill=colors["badge_bg"],
    )
    # 💡 用 anchor="mm" 確保文字在按鈕內垂直置中
    if len(cta_wrapped) == 1:
        draw.text((IMG_W // 2, y + btn_h // 2), cta_wrapped[0],
                  font=cta_font, fill=colors["badge_text"], anchor="mm")
    else:
        text_y = y + btn_pad_y
        for i, wl in enumerate(cta_wrapped):
            draw.text((IMG_W // 2, text_y + cta_line_heights[i] // 2), wl,
                      font=cta_font, fill=colors["badge_text"], anchor="mm")
            text_y += cta_line_heights[i] + cta_line_spacing
    y += btn_h + 40

    # 追蹤提示
    draw.text((IMG_W // 2, y), follow_text, font=follow_font, fill=colors["muted"], anchor="mt")


# ── sanitize ──────────────────────────────────────────────────

def _sanitize_slide(slide: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for k, v in slide.items():
        if isinstance(v, str):
            sanitized[k] = _replace_emoji(v)
        elif isinstance(v, list):
            sanitized[k] = [_replace_emoji(i) if isinstance(i, str) else i for i in v]
        else:
            sanitized[k] = v
    return sanitized


# ── 主要渲染 ──────────────────────────────────────────────────

def render_slide(slide: dict[str, Any], index: int, total: int, output_path: Path) -> None:
    """渲染單張 slide，自動決定背景主題。"""
    slide = _sanitize_slide(slide)
    slide_type = slide.get("type", "title")

    theme = _get_slide_theme(slide_type, index, total)
    img, draw = _create_canvas(theme)
    colors = _theme_colors(theme)

    if slide_type == "title":
        _draw_title_slide(img, draw, slide, colors)
    elif slide_type == "bullet_list":
        _draw_bullet_list_slide(img, draw, slide, colors)
    elif slide_type == "numbered":
        _draw_numbered_slide(img, draw, slide, colors)
    elif slide_type == "case_study":
        _draw_case_study_slide(img, draw, slide, colors)
    elif slide_type == "summary":
        _draw_summary_slide(img, draw, slide, colors)
    elif slide_type == "cta":
        _draw_cta_slide(img, draw, slide, colors)
    else:
        _draw_title_slide(img, draw, slide, colors)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")


def generate_images(content: dict[str, Any], output_subdir: str | None = None) -> list[Path]:
    """產生所有 slide 圖片。

    Args:
        content: 含 "slides" 陣列的 dict（來自 content_generator）
        output_subdir: 輸出子目錄名稱

    Returns:
        輸出檔案路徑列表
    """
    if output_subdir:
        out_dir = OUTPUT_DIR / output_subdir
    else:
        out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    slides = content.get("slides", [])
    total = len(slides)

    for i, slide in enumerate(slides):
        out_path = out_dir / f"slide_{i + 1:02d}.png"
        slide_type = slide.get("type", "title")
        theme = _get_slide_theme(slide_type, i, total)
        logger.info("  slide_%02d.png (type=%s, theme=%s)", i + 1, slide_type, theme)
        render_slide(slide, i, total, out_path)
        paths.append(out_path)

    logger.info("圖片產生完成：%d 張 → %s", len(paths), out_dir)
    return paths

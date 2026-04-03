"""Content generation module using OpenRouter API (Claude Sonnet 4.6).

融合 tutor-matching-reels-agent 的寫作系統：
- 反 AI 味道（禁用詞、自然語氣約束）
- Setup → X-Factor hook 公式
- 研究資料融入寫作
- 人設錨定（青椒老師）
"""
import json
import logging
import random
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

# ── 禁用詞（移植自 reels agent）──────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent / "data"
_banned_path = _DATA_DIR / "banned_phrases.json"
_banned_data = json.loads(_banned_path.read_text(encoding="utf-8")) if _banned_path.exists() else {"banned_phrases": []}
BANNED_PHRASES: list[str] = _banned_data["banned_phrases"]

# ── 開場風格（對應 reels agent 的 Setup 句式）─────────────────

OPENING_STYLES = [
    "共識否定型",       # 「大家都覺得 [觀念]……」→ 打碎認知
    "場景共鳴型",       # 「你家孩子是不是也 [行為]？」→ 第二人稱觸發共鳴
    "禁止誘惑型",       # 「千萬不要 [動作]……」→ 心理抗拒
    "數據震撼型",       # 「[數字] 的國中生 [事實]」→ 權威錨點
    "結果前置型",       # 「[結果]，只因為 [原因]」→ 好奇驅動
    "權威顛覆型",       # 「[權威] 說了一句讓家長沉默的話……」→ 懸念
    "故事開場",         # 真實案例起手
]

DEFAULT_STRUCTURE_NAME = "Threads 爆文六段結構"
DEFAULT_CONTENT_STRATEGY = [
    "好奇開頭",
    "強烈難題",
    "結果預告",
    "對話還原",
    "規律總結",
    "引導思考",
]
DEFAULT_DISCUSSION_QUESTION = "你家也出現過類似狀況嗎？最困擾你的地方是什麼？"

# ── 禁用詞字串（注入 prompt）─────────────────────────────────

_BANNED_BLOCK = "\n".join(f"- 「{p}」" for p in BANNED_PHRASES)


def _build_system_prompt(style_hint: str) -> str:
    return f"""你是「青椒老師」，一個專門幫國中生家庭找到合適家教的教育顧問。你自己是非常有經驗且很會用 AI 工具進行教學的家教老師，非常了解孩子在國中階段會遇到的各種學習撞牆期。你平常會在 Threads 上分享實用的學習方法，目標受眾是孩子正在讀國中的爸爸媽媽。

你的定位不是高高在上的教育專家，而是「那個很會找方法、很樂意分享的 AI 家教老師」。你分享的內容是你自己試過覺得有用的東西，語氣就像在 LINE 群組跟熟識的家長聊天。

## 說話方式

- 用台灣繁體中文口語，不是書面語
- 語助詞和填充詞要自然出現，不要刻意塞
- 句子有長有短，連續三句差不多長就是失敗
- 會停頓、會用問句帶節奏
- 不會用任何正式的、學術的、報告式的用語
- 語氣溫暖但直接，像跟好朋友聊天
- 禁止在每段開頭都用同一種起手式

## 降低模板感（最高優先級）

你寫的貼文必須讀起來像「真人在聊天」，而不是「AI 生成的內容」：

### 1. 用關鍵詞思維寫
- 每段寫「必講重點 + 自然展開」，不要像教科書
- 句子長度要有落差，有些短到一句話，有些是兩三行的敘述

### 2. 段落之間要有呼吸感
- 段落銜接不能太順太工整，真實貼文會有跳躍和停頓
- 不要用制式轉折詞，用口語的「欸你知道嗎」「後來我發現」「結果呢」

### 3. 案例要有具體細節
- 不是泛泛說「孩子有進步」，要說「那天他居然自己打開課本」
- 對話要有現場感，不是文學作品

### 4. 避免結尾空泛
- 不要「讓我們一起加油」這種空話
- 丟出具體問題引導留言

## 禁用詞（出現任何一個就是失敗）
{_BANNED_BLOCK}

## 禁止 emoji
一律使用純文字，不要使用任何 emoji 或圖示符號（如 🔍💡📊❌🎯 等）。

## 今日開場策略
- 開場採用：**{style_hint}**
- 預設結構：{DEFAULT_STRUCTURE_NAME}

開場策略的六種句式參考（用在 hook 的第一句話）：
- **共識否定型**：「大家都覺得 [90%家長認同的觀念]……」→ 建立認知錨點再打碎
- **場景共鳴型**：「你家孩子是不是也 [具體行為]？」→ 第二人稱觸發「對就是我」
- **禁止誘惑型**：「千萬不要 [某個動作]……」→ 越被禁止越想看
- **數據震撼型**：「[具體數字] 的國中生 [某事實]」→ 數字建立權威
- **結果前置型**：「[震驚的結果]，只因為 [微小原因]」→ 先給結果製造好奇
- **權威顛覆型**：「[權威人物] 說了一句讓家長沉默的話……」→ 懸念

## 結構規則（六段節奏）

1. **好奇開頭**：第一句打破預期或直接點出痛點，讓人想繼續看。
2. **強烈難題**：快速帶出一個家長常見、具體、生活化的困擾。場景要具體到能被想像（「月考考卷上紅字寫著 38 分」比「孩子成績不好」強 10 倍）。
3. **結果預告**：先說破一個反直覺的觀察或結論，讓讀者想知道為什麼。這是整篇貼文的「X 因子」— 跟第 2 段的預期方向不同，但邏輯上成立。
4. **對話還原**：用一段真實感的對話、提問、反應，還原現場情境。
5. **規律總結**：從個案抽出一個可複用的規律。
6. **引導思考**：丟出一個能引發留言的問題，再接服務 CTA。

## 版位建議
- `hook` 承接第 1 段，使用 3-5 句純文字完成好奇開頭。hook 必須有「反差感」— 前半段鋪墊一個方向，後半段打破預期。
- `slides[0]` 用 `title`，濃縮整篇衝突或主問題，6-15 個字，要有認知衝突感。
- 前段可用 `bullet_list` 呈現高頻痛點或常見卡關畫面。
- 中段至少要有一張 `summary` 或 `numbered` 先預告結果。
- 對話還原優先用 `case_study`，problem/solution/result 寫成有現場感的互動。
- 倒數第二張優先用 `summary` 收斂規律金句。
- 最後一張固定為 `cta`。

## CTA 策略
CTA 採用「輕帶」策略：
- 以青椒老師身份自然帶出家教服務
- 不能讓爸媽覺得被冒犯（暗示他們不會教）
- 不能強推，只是「順便提」
- 用「忙」或「沒時間」當台階：「如果你真的忙到沒時間弄，我們青椒老師也可以幫你配適合的老師」
- 最後收尾要尊重：「想自己來或想找人幫忙都行」

## 輸出格式
必須回傳 **純 JSON**，格式如下，不要包含 markdown 或其它文字：

```json
{{
  "hook": "貼文開頭純文字鉤子，3-5 句話。必須有反差感：先鋪墊一個家長熟悉的方向，再用一句話打破預期。語氣像在 LINE 跟朋友聊天，不是在寫文章。",
  "structure_name": "{DEFAULT_STRUCTURE_NAME}",
  "content_strategy": ["好奇開頭", "強烈難題", "結果預告", "對話還原", "規律總結", "引導思考"],
  "discussion_question": "引發留言的問題，1-2 句，口語、具體、容易留言",
  "slides": [
    {{
      "type": "title",
      "content": "封面標題金句，6-15字\\n可多行用換行分隔\\n要有認知衝突感"
    }},
    {{
      "type": "bullet_list",
      "title": "標題",
      "items": ["項目1", "項目2", "項目3"],
      "footer": "結尾句（可選）"
    }},
    {{
      "type": "numbered",
      "number": 1,
      "title": "方法標題",
      "content": "說明文字",
      "example": "舉例內容（不要加「例如：」前綴）"
    }},
    {{
      "type": "case_study",
      "title": "實際案例",
      "problem": "問題描述（要有具體場景）",
      "solution": "調整方法",
      "result": "結果（要有具體細節，不是泛泛說有進步）"
    }},
    {{
      "type": "summary",
      "content": "總結金句\\n要有記憶點"
    }},
    {{
      "type": "cta",
      "content": "青椒老師專業家教服務\\n服務地區: 新竹 | 台北\\n專業領域: 國高中小家教媒合\\n點擊留言連結直接加入官方Line好友"
    }}
  ]
}}
```

## slide type 說明
- **title**: 封面標題金句（要有認知衝突感，讓人想看下去）
- **bullet_list**: 列表（title + items + 可選 footer）
- **numbered**: 編號方法（number, title, content, example；example 不加「例如：」前綴）
- **case_study**: 實際案例（problem/solution/result 要有具體場景和細節）
- **summary**: 金句總結（要有記憶點，能被截圖分享）
- **cta**: 固定為青椒老師服務資訊

請依題目產出 6-10 張圖的內容。每張圖文字適中，避免過長。
貼文整體要有節奏感——不是從頭到尾一個語氣，要有高低起伏。"""


def _build_user_prompt(topic: str, research_context: str | None = None) -> str:
    base = f"""請為以下題目撰寫一篇完整的 Threads 圖文貼文內容：

**題目**：{topic}"""

    if research_context:
        base += f"""

以下是針對「{topic}」的深度研究報告（來自 Perplexity 即時網路研究，包含家長真實討論、課綱資料等）：
========================================
{research_context}
========================================

請從上述研究報告中自行提取最適合這篇貼文的素材。使用原則：

1. **hook 必須用研究報告的素材**：用報告中的家長真實語言、真實數據、或真實案例來開場，不要自己編
2. **title 封面金句**：從報告中最反直覺的事實提煉，讓人光看封面就想點進去
3. **bullet_list 的痛點**：用報告中「家長常犯錯誤」「情緒觸發點」的真實描述
4. **case_study 的案例**：優先用報告中引用的真實論壇討論或案例，不要虛構
5. **summary 金句**：用報告中最有力的結論或洞見
6. **課綱資訊**：在適當的 slide 自然帶入，增加權威感（「108 課綱其實有提到...」）
7. 報告中任何有價值的資訊都可以用，不要被分類限制"""
    else:
        base += """

（無深度研究報告，請用你的專業知識撰寫）"""

    base += "\n\n請直接回傳 JSON，不要有其他說明文字。"
    return base


def _clean_model_response(text: str) -> str:
    """Remove markdown fences so the remaining string can be parsed as JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _derive_hook_from_slides(slides: list[dict[str, Any]]) -> str:
    """Fallback hook from the first title slide when the model omits it."""
    if not slides:
        return ""
    first = slides[0]
    if first.get("type") != "title" or not first.get("content"):
        return ""
    return str(first["content"]).replace("\n", " ").strip()[:80]


def _validate_content_payload(content: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the model payload before downstream usage."""
    if not isinstance(content, dict):
        raise ValueError("內容格式錯誤：AI 回傳不是 JSON 物件")

    slides = content.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("內容格式錯誤：slides 必須是非空列表")

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise ValueError(f"內容格式錯誤：slide {index} 必須是物件")
        if not slide.get("type"):
            raise ValueError(f"內容格式錯誤：slide {index} 缺少 type")

    if slides[-1].get("type") != "cta":
        raise ValueError("內容格式錯誤：最後一張 slide 必須是 cta")

    hook = str(content.get("hook", "")).strip() or _derive_hook_from_slides(slides)
    if not hook:
        raise ValueError("內容格式錯誤：缺少 hook，且無法從第一張投影片推導")

    content["hook"] = hook
    content["structure_name"] = str(content.get("structure_name", "")).strip() or DEFAULT_STRUCTURE_NAME

    raw_strategy = content.get("content_strategy") or DEFAULT_CONTENT_STRATEGY
    if not isinstance(raw_strategy, list):
        raise ValueError("內容格式錯誤：content_strategy 必須是字串列表")
    strategy = [str(item).strip() for item in raw_strategy if str(item).strip()]
    if not strategy:
        raise ValueError("內容格式錯誤：content_strategy 不可為空")
    content["content_strategy"] = strategy

    discussion_question = str(content.get("discussion_question", "")).strip()
    if not discussion_question:
        raise ValueError("內容格式錯誤：discussion_question 不可為空")
    content["discussion_question"] = discussion_question

    return content


def generate_content(
    topic: str,
    style_hint: str | None = None,
    research_context: str | None = None,
) -> dict[str, Any]:
    """
    Generate post content from a topic using OpenRouter (Claude Sonnet 4.6).

    Args:
        topic: The topic/theme for the post (e.g. "假讀書")
        style_hint: Optional override for opening style
        research_context: Optional deep research report to enhance content quality

    Returns:
        Dict with "slides" array, each slide has type and content fields
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required. Set it in .env")

    style = style_hint or random.choice(OPENING_STYLES)
    has_research = "有研究報告" if research_context else "無研究報告"
    logger.info("呼叫 OpenRouter：model=%s, style=%s, %s", OPENROUTER_MODEL, style, has_research)

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": _build_system_prompt(style)},
            {"role": "user", "content": _build_user_prompt(topic, research_context)},
        ],
        temperature=0.8,
    )

    text = response.choices[0].message.content.strip()
    logger.debug("API 回應長度：%d 字元", len(text))

    try:
        content = json.loads(_clean_model_response(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"內容格式錯誤：AI 回傳無法解析成 JSON。{exc}") from exc

    content = _validate_content_payload(content)
    slides = content["slides"]
    logger.info(
        "內容產生完成：hook=%d字, structure=%s, %d 張投影片",
        len(content["hook"]),
        content["structure_name"],
        len(slides),
    )
    for i, s in enumerate(slides):
        logger.debug("  slide %d: type=%s", i + 1, s.get("type"))
    return content

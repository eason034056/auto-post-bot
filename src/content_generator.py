"""Content generation module using OpenRouter API (Claude Sonnet 4.6)."""
import json
import logging
import random
from typing import Any

from openai import OpenAI

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

# Writing style options for variety (plan: 寫作多樣化)
OPENING_STYLES = [
    "親子對話開場",
    "痛點提問",
    "數據開場",
    "情境描述",
    "金句開場",
    "反問開場",
    "故事開場",
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


def _build_system_prompt(style_hint: str) -> str:
    return f"""你是青椒家教（清大、交大家教老師團隊）的社群小編，專門為 Threads 撰寫吸引國中家長的圖文貼文。

## 目標客群
國中家長，關心孩子的學習成效與讀書方法。

## 今日寫作風格
- 開場採用：{style_hint}
- 預設結構：{DEFAULT_STRUCTURE_NAME}

## 重要原則
1. **寫作多樣化**：勿固定模板，依題目與今日風格自由發揮
2. **口語化**：避免學術用語，用家長日常會說的句子
3. **同理心**：先肯定孩子有在努力，再談方法
4. **權威背書**：可適度提及「清大、交大家教老師」
5. **禁止 emoji**：一律使用純文字，不要使用任何 emoji 或圖示符號（如 🔍💡📊❌🎯 等）

## 結構規則
請以以下節奏作為整篇貼文的預設骨架，保持節奏固定、措辭靈活：
1. **好奇開頭**：第一句要讓人想繼續看，或直接點出這篇是寫給誰的。
2. **強烈難題**：快速帶出一個家長常見、具體、生活化的困擾。
3. **結果預告**：先說破一個關鍵觀察或結論，讓讀者想知道為什麼。
4. **對話還原**：用一段真實感的對話、提問、反應，還原現場情境。
5. **規律總結**：從個案抽出一個可複用的規律，不只講單一故事。
6. **引導思考**：最後丟出一個能引發留言的問題，再接服務 CTA。

## 版位建議
- `hook` 承接第 1 段，使用 3-5 句純文字完成好奇開頭與讀者過濾。
- `slides[0]` 用 `title`，濃縮整篇衝突或主問題。
- 前段可用 `bullet_list` 呈現高頻痛點或常見卡關畫面。
- 中段至少要有一張 `summary` 或 `numbered` 先預告結果。
- 對話還原優先用 `case_study`，把 `problem`、`solution`、`result` 寫成有現場感的互動。
- 倒數第二張優先用 `summary` 收斂規律。
- 最後一張固定為 `cta`。

## 輸出格式
必須回傳 **純 JSON**，格式如下，不要包含 markdown 或其它文字：

```json
{{
  "hook": "第一段純文字鉤子，3-5 句話，吸引人繼續往下滑看圖片。例如：孩子明明有在讀書，為什麼成績還是上不去？很多家長都有這個疑問。其實背後可能跟讀書方法、專注力、或是壓力有關，值得我們一起來了解。",
  "structure_name": "{DEFAULT_STRUCTURE_NAME}",
  "content_strategy": ["好奇開頭", "強烈難題", "結果預告", "對話還原", "規律總結", "引導思考"],
  "discussion_question": "最後要引發留言討論的問題，1-2 句，口語、具體、容易留言",
  "slides": [
    {{
      "type": "title",
      "content": "此圖要顯示的文字，可多行用換行分隔"
    }},
    {{
      "type": "bullet_list",
      "title": "標題（可選）",
      "items": ["項目1", "項目2"],
      "footer": "結尾句（可選）"
    }},
    {{
      "type": "numbered",
      "number": 1,
      "title": "方法標題",
      "content": "說明文字",
      "example": "舉例內容（不要加「例如：」前綴，系統會自動加上）"
    }},
    {{
      "type": "case_study",
      "title": "實際案例",
      "problem": "問題描述",
      "solution": "調整方法",
      "result": "結果"
    }},
    {{
      "type": "summary",
      "content": "總結金句或要點"
    }},
    {{
      "type": "cta",
      "content": "青椒老師專業家教服務\\n服務地區: 新竹 | 台北\\n專業領域: 國高中小家教媒合\\n點擊留言連結直接加入官方Line好友"
    }}
  ]
}}
```

## 欄位說明
- **hook**（必填）：貼文開頭純文字，3-5 句話，作為鉤子吸引人繼續看圖片。這段會顯示在圖片之前。
- **structure_name**（必填）：固定填 `{DEFAULT_STRUCTURE_NAME}`
- **content_strategy**（必填）：固定填這篇使用的 6 段節奏
- **discussion_question**（必填）：放在結果頁讓小編可直接複製，用來引導留言
- **slides**：圖文內容，每張圖對應一個 slide

## slide type 說明
- **title**: 第一張圖的標題、金句（單一區塊文字）
- **bullet_list**: 列表（可選 title, items, footer）
- **numbered**: 編號方法（number, title, content, example 可選；example 只放舉例內容，不要加「例如：」前綴）
- **case_study**: 實際案例（可選，problem/solution/result）
- **summary**: 總結
- **cta**: 固定為青椒家教服務資訊，最後一張圖

請依題目產出 6-10 張圖的內容，每張圖文字適中，避免過長。
如果題目本身不適合強烈故事，也仍要保留這 6 段節奏，但措辭可以更自然，不要出現模板感。"""


def _build_user_prompt(topic: str, research_context: str | None = None) -> str:
    # 基本 prompt
    base = f"""請為以下題目撰寫一篇完整的 Threads 圖文貼文內容：

**題目**：{topic}"""

    # 💡 有研究報告時，注入真實數據讓 AI 寫作更有深度
    if research_context:
        base += f"""

**以下是針對此主題的深度研究報告，請務必參考並融入你的貼文內容中：**

========================================
{research_context}
========================================

**使用研究報告的原則：**
1. 優先引用報告中的「家長真實語言」作為 hook 和對話素材
2. 用報告中的具體案例來寫 case_study，不要自己編
3. 引用報告中的課綱資訊增加權威感
4. 用報告中的情緒觸發點來設計好奇開頭
5. 常見迷思可以作為「強烈難題」的素材"""

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

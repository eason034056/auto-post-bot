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

STRUCTURE_HINTS = [
    "方法數量 2-4 個皆可",
    "可省略實際案例，改為「研究指出」",
    "可省略案例，直接總結",
    "問題定義用常見迷思呈現",
]


def _build_system_prompt(style_hint: str, structure_hint: str) -> str:
    return f"""你是青椒家教（清大、交大家教老師團隊）的社群小編，專門為 Threads 撰寫吸引國中家長的圖文貼文。

## 目標客群
國中家長，關心孩子的學習成效與讀書方法。

## 今日寫作風格
- 開場採用：{style_hint}
- 結構提示：{structure_hint}

## 重要原則
1. **寫作多樣化**：勿固定模板，依題目與今日風格自由發揮
2. **口語化**：避免學術用語，用家長日常會說的句子
3. **同理心**：先肯定孩子有在努力，再談方法
4. **權威背書**：可適度提及「清大、交大家教老師」
5. **禁止 emoji**：一律使用純文字，不要使用任何 emoji 或圖示符號（如 🔍💡📊❌🎯 等）

## 輸出格式
必須回傳 **純 JSON**，格式如下，不要包含 markdown 或其它文字：

```json
{{
  "hook": "第一段純文字鉤子，3-5 句話，吸引人繼續往下滑看圖片。例如：孩子明明有在讀書，為什麼成績還是上不去？很多家長都有這個疑問。其實背後可能跟讀書方法、專注力、或是壓力有關，值得我們一起來了解。",
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
- **slides**：圖文內容，每張圖對應一個 slide

## slide type 說明
- **title**: 第一張圖的標題、金句（單一區塊文字）
- **bullet_list**: 列表（可選 title, items, footer）
- **numbered**: 編號方法（number, title, content, example 可選；example 只放舉例內容，不要加「例如：」前綴）
- **case_study**: 實際案例（可選，problem/solution/result）
- **summary**: 總結
- **cta**: 固定為青椒家教服務資訊，最後一張圖

請依題目產出 8-10 張圖的內容，每張圖文字適中，避免過長。"""


def _build_user_prompt(topic: str) -> str:
    return f"""請為以下題目撰寫一篇完整的 Threads 圖文貼文內容：

**題目**：{topic}

請直接回傳 JSON，不要有其他說明文字。"""


def generate_content(topic: str, style_hint: str | None = None) -> dict[str, Any]:
    """
    Generate post content from a topic using OpenRouter (Claude Sonnet 4.6).

    Args:
        topic: The topic/theme for the post (e.g. "假讀書")
        style_hint: Optional override for opening style

    Returns:
        Dict with "slides" array, each slide has type and content fields
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required. Set it in .env")

    style = style_hint or random.choice(OPENING_STYLES)
    structure = random.choice(STRUCTURE_HINTS)
    logger.info("呼叫 OpenRouter：model=%s, style=%s, structure=%s", OPENROUTER_MODEL, style, structure)

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": _build_system_prompt(style, structure)},
            {"role": "user", "content": _build_user_prompt(topic)},
        ],
        temperature=0.8,
    )

    text = response.choices[0].message.content.strip()
    logger.debug("API 回應長度：%d 字元", len(text))

    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    content = json.loads(text)
    slides = content.get("slides", [])
    # hook 為貼文開頭純文字鉤子；若模型未回傳，從第一張圖標題衍生
    hook = content.get("hook", "").strip()
    if not hook and slides:
        first = slides[0]
        if first.get("type") == "title" and first.get("content"):
            hook = first["content"].replace("\n", " ").strip()[:80]
    logger.info("內容產生完成：hook=%d字, %d 張投影片", len(hook), len(slides))
    for i, s in enumerate(slides):
        logger.debug("  slide %d: type=%s", i + 1, s.get("type"))
    return content

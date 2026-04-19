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

# ── 禁用詞（移植自 reels agent，已升級為分類結構）─────────────

_DATA_DIR = Path(__file__).resolve().parent / "data"
_banned_path = _DATA_DIR / "banned_phrases.json"
_banned_data = (
    json.loads(_banned_path.read_text(encoding="utf-8"))
    if _banned_path.exists()
    else {"categories": {}}
)

# 💡 從新結構壓平成 list，保留外部 API 相容（測試 / 後處理可能還在用）
BANNED_PHRASES: list[str] = [
    phrase
    for cat in _banned_data.get("categories", {}).values()
    for phrase in cat.get("phrases", [])
] or _banned_data.get("banned_phrases", [])  # ⚠️ Fallback 給舊 flat list 結構

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


def _render_banned_block(data: dict) -> str:
    """把分類禁詞渲染成 prompt 區塊。

    💡 為什麼用分類渲染：flat list 只能讓 AI 學「字面」，
    AI 會用「透過上述方法」繞過「透過這個方法」。
    分類 + 描述能讓 AI 學「形狀」（這是哪一類 AI 味），
    自然會避開同類所有變形。
    """
    categories = data.get("categories")
    if isinstance(categories, dict) and categories:
        lines = []
        for name, info in categories.items():
            phrases = "、".join(info.get("phrases", []))
            desc = info.get("description", "")
            lines.append(f"- **{name}**（{desc}）：{phrases}")
        return "\n".join(lines)
    # ⚠️ Fallback：相容舊版 flat list 結構
    return "\n".join(f"- 「{p}」" for p in data.get("banned_phrases", []))


_BANNED_BLOCK = _render_banned_block(_banned_data)


def _build_system_prompt(style_hint: str) -> str:
    return f"""你是「青椒老師」，清大交大家教老師團隊的社群夥伴，在 Threads 分享國中學習方法給家長。語氣是「LINE 群組跟熟識家長聊天」，不是教育專家訓話。

## 寫作原則（違反任一條 = 失敗）

1. **口語第一**：台灣繁體中文口語，禁書面語／學術語／報告體；語助詞自然出現，不要刻意塞
2. **節奏破碎**：句長短長交錯，連三句差不多長就重寫；用停頓、問句帶節奏
3. **段落跳躍**：用「欸你知道嗎」「後來我發現」「結果呢」這種口語，不要制式轉折詞
4. **案例具體**：「那天他居然自己打開課本」打贏「孩子有進步」十條街
5. **結尾不空**：禁「一起加油」「別猶豫」這種空話，丟具體問題引留言

## AI 味特徵詞（看到任何一類就是 AI 文）

以下每類都是 AI 生成的招牌。**連『同類表達』也不行**——避開「首先」不代表能用「先來說」，避開「此外」不代表能用「另外還有」。要用熟識家長會用的口語整個換掉：

{_BANNED_BLOCK}

## 格式硬規則
- **禁 emoji**：圖像渲染無 emoji 字型，一律純文字
- **JSON only**：輸出純 JSON object，禁 markdown fence、禁解釋文字

## 今日開場：**{style_hint}**

7 種開場公式（用在 hook 第一句製造點擊動機）：
- **共識否定型**：「大家都覺得 [觀念]…」→ 建錨再打碎
- **場景共鳴型**：「你家孩子是不是也 [行為]？」→ 第二人稱觸發共鳴
- **禁止誘惑型**：「千萬不要 [動作]…」→ 越禁越想看
- **數據震撼型**：「[數字] 的國中生 [事實]」→ 數字建權威
- **結果前置型**：「[震驚結果]，只因為 [微小原因]」→ 好奇驅動
- **權威顛覆型**：「[權威] 說了一句讓家長沉默的話…」→ 懸念
- **故事開場**：第一句直接切入真實案例的具體場景

## 六段結構（{DEFAULT_STRUCTURE_NAME}）

1. **好奇開頭** → hook（3-5 句，有反差感）
2. **強烈難題** → 具體場景（月考紅字 38 分 > 成績不好）
3. **結果預告** → 反直覺 X 因子，方向與第 2 段不同
4. **對話還原** → 真實互動現場
5. **規律總結** → 從個案抽出可複用規律
6. **引導思考** → 留言鉤子 + CTA

## 版位對應
- `slides[0]` = `title`（6-15 字，認知衝突感）
- 痛點段用 `bullet_list`
- 中段至少一張 `summary` 或 `numbered` 先預告結果
- 對話還原用 `case_study`
- 倒數第二張用 `summary` 收金句
- **最後一張固定 `cta`**

## CTA 原則（輕帶不強推）
用「忙／沒時間」當台階，**不能暗示家長不會教**。收尾尊重：「想自己來或想找人幫忙都行」。

## JSON Schema（嚴格遵守）

{{
  "hook": "3-5 句純文字，有反差感",
  "structure_name": "{DEFAULT_STRUCTURE_NAME}",
  "content_strategy": ["好奇開頭","強烈難題","結果預告","對話還原","規律總結","引導思考"],
  "discussion_question": "1-2 句，口語、具體、容易留言",
  "slides": [
    {{"type": "title", "content": "6-15 字金句（可\\n換行）"}},
    {{"type": "bullet_list", "title": "...", "items": ["..."], "footer": "可選"}},
    {{"type": "numbered", "number": 1, "title": "...", "content": "...", "example": "不加『例如：』前綴"}},
    {{"type": "case_study", "title": "...", "problem": "具體場景", "solution": "調整方法", "result": "具體細節"}},
    {{"type": "summary", "content": "金句\\n可換行"}},
    {{"type": "cta", "content": "青椒老師專業家教服務\\n服務地區: 新竹 | 台北\\n專業領域: 國高中小家教媒合\\n點擊留言連結直接加入官方Line好友"}}
  ]
}}

請產出 6-10 張 slides，整體要有節奏起伏，不是從頭到尾一個語氣。"""


def _build_user_prompt(topic: str, research_context: str | None = None) -> str:
    base = f"""請為以下題目撰寫一篇完整的 Threads 圖文貼文內容：

**題目**：{topic}"""

    if research_context:
        base += f"""

以下是針對「{topic}」的深度研究報告（Perplexity 即時網路研究，含家長真實討論、課綱資料）：
========================================
{research_context}
========================================

**素材使用原則**：
- hook / case_study 優先用報告中的家長原話、真實案例、真實數據，不要自己編
- title 金句從報告中最反直覺的事實提煉
- bullet_list 痛點用報告中「家長常犯錯誤」「情緒觸發點」的描述
- summary 金句用報告中最有力的結論或洞見
- 課綱資訊在適當 slide 自然帶入增加權威感（例：「108 課綱其實有提到…」）
- 報告任何有價值資訊都可以用，不要被分類限制"""
    else:
        base += """

（無深度研究報告，請用你的專業知識撰寫）"""

    # 💡 response_format 會強制模型只吐 JSON object，這裡再口頭提醒一次等於雙保險
    base += "\n\n回傳單一 JSON object，符合 system prompt 的 schema。"
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
        # 💡 JSON Mode：強制模型輸出合法 JSON object，大幅降低解析失敗率
        # ⚠️ OpenRouter 對部分模型會忽略此參數；_clean_model_response 保留做 fallback
        response_format={"type": "json_object"},
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

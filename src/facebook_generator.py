"""Facebook 貼文內容生成器（與 content_generator.py 平行的模組）。

為什麼獨立一個模組，而不是在 content_generator 裡加 platform 參數：
- Threads/IG 的產物是「短 hook + 多張 slide」，目的是勾人「滑圖」
- Facebook 的產物是「一篇完整中長文 + 一張封面」，文字本身就是主體
兩者的 prompt、JSON schema、產物形狀差異夠大，混在一個函式會長出大片
if/else 分支。只有 2 個平台時，平行模組比抽象層（Strategy Pattern）更好維護
（Rule of Three：等第 3 個平台才考慮抽象）。

複用策略：禁詞區塊、JSON 清洗、開場公式這些「跟平台無關」的寫作資產，
直接 import content_generator 既有的，不重寫。
"""
import json
import logging
import random
from typing import Any

from openai import OpenAI

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

# 💡 直接複用 content_generator 的寫作資產（禁詞 / JSON 清洗 / 開場公式），
#    避免兩套禁詞各自漂移，未來改禁詞只要改一處。
from .content_generator import (
    _BANNED_BLOCK,
    _clean_model_response,
    OPENING_STYLES,
)

logger = logging.getLogger(__name__)

# FB 文章字數區間（驗證用）。目標 300-500，但給 AI 一點容忍區間避免動不動就失敗。
FB_ARTICLE_MIN = 250
FB_ARTICLE_MAX = 600


def _build_system_prompt(style_hint: str) -> str:
    return f"""你是「青椒老師」，清大交大家教老師團隊的社群夥伴，在 Facebook 分享國中學習方法給家長。語氣是「跟熟識家長聊天」，不是教育專家訓話。

## 任務：寫一篇 Facebook 動態貼文
和 Threads 不同：Facebook 是「一篇完整的文，配一張封面圖」。**文章本身就是主體**，要能讓家長在動態牆上一路讀完，不是只丟個鉤子叫人去別的地方看。

## 文章規格（違反任一條 = 失敗）
1. **長度 300-500 字**（繁體中文字數）。太短沒料、太長沒人讀完
2. **完整起承轉合**，建議 4-5 段，段落之間用空行（`\\n\\n`）分隔：
   - 起：用今日開場公式切入，第一句就要讓家長停下來
   - 承：一個**具體**情境 / 具名案例落地（不要「很多家長都…」這種擴張敘述）
   - 轉：點出反差、洞察或機制（為什麼會這樣）
   - 合：給一個可操作的小方法或結論
   - 收：丟一個具體問題引導留言（不要「一起加油」這種空話）
3. **口語第一**：台灣繁中口語，禁書面語／報告體；句長短長交錯
4. **案例具體**：「那天他自己打開課本訂正到十點」打贏「孩子有進步」十條街
5. 文章是純文字貼文，**emoji 可少量但不強求**，不要整篇塞滿

## 今日開場：**{style_hint}**
9 種開場公式（用在第一句製造停留動機）：
情緒勾子型：共識否定型、場景共鳴型、禁止誘惑型、數據震撼型、結果前置型、權威顛覆型、故事開場
知識價值型：數據揭露型、機制解釋型（適合有研究/方法為主的主題，第一句就給家長有用資訊）

## 禁抽象形容詞（機器感主因）
禁用空話形容詞：「關鍵的、重要的、有效的、顯著的、明顯的、大幅、極大、革命性、突破性、全方位、全面、卓越、優異、極致」。
每個好處用具體畫面取代：
- ❌「成績明顯提升」→ ✅「月考數學從 38 分爬到 67 分」
- ❌「孩子變得更自律」→ ✅「晚上十點我去看，他自己還在訂正」

## AI 味特徵詞（看到任何一類就是 AI 文，連同類表達也不行）
{_BANNED_BLOCK}

## 封面圖（cover）規格
封面是一張橫式圖，會用程式渲染成圖片，所以：
- **嚴禁 emoji**（圖像字型無 emoji）
- `title`：封面主標，**≤ 14 字**，要有點擊衝動（可與文章第一句呼應但不要照抄）
- `subtitle`：一句副文，**≤ 20 字**，補述或勾住
- `tag`：小標籤 2-6 字，可中英並陳（推薦），例：「方法 / METHOD」「觀點 / INSIGHT」「案例 / CASE」

## CTA 原則
文章結尾不要硬推業配。用「忙／沒時間」當台階，不暗示家長不會教，收尾尊重。
（加 LINE 的引導由置頂留言處理，文章本身專心把內容講好。）

## 格式硬規則
- **JSON only**：輸出純 JSON object，禁 markdown fence、禁解釋文字

## JSON Schema（嚴格遵守）
{{
  "article": "300-500 字的完整 Facebook 文章本文，段落用 \\n\\n 分隔",
  "cover": {{"tag": "觀點 / INSIGHT", "title": "封面主標 ≤14字", "subtitle": "副文 ≤20字"}},
  "discussion_question": "**at most 2 句**，口語、具體、容易留言"
}}

回傳單一 JSON object。"""


def _build_user_prompt(topic: str, research_context: str | None = None) -> str:
    base = f"""請為以下題目撰寫一篇完整的 Facebook 貼文（文章本文 + 封面）：

**題目**：{topic}"""

    if research_context:
        base += f"""

以下是針對「{topic}」的實證導向深度研究報告（含事實基礎 / 觀點光譜 / 實證方法 / 引用來源）：
========================================
{research_context}
========================================

**素材使用原則**（嚴格執行）：
- 文章優先用：量化事實 / 有研究支持的洞察 / 具名專家的反直覺結論（禁憑空推論）
- 每個事實主張帶出來源類型，例：「研究顯示…」「108 課綱明訂…」「親子天下訪談某國中老師指出…」
- 研究報告沒提到的數字**不要自己編**，寧可不說數字也不捏造
- 案例用具名專家 / 學術個案 / 具名教師觀察；**禁用**「一位家長分享」「有位媽媽說」這類無法驗證的匿名敘述
- 開場若研究以事實 / 方法為主（情緒素材少）→ 優先用「數據揭露型」或「機制解釋型」，讓家長第一句就覺得「我學到東西了」"""
    else:
        base += """

（無深度研究報告，請用你的專業知識撰寫）"""

    base += "\n\n回傳單一 JSON object，符合 system prompt 的 schema。"
    return base


def _validate_facebook_payload(content: dict[str, Any]) -> dict[str, Any]:
    """驗證並正規化 FB 生成結果。

    ⚠️ 字數用 len(去掉空白) 粗估，不追求精準——只是擋掉「明顯太短沒料」
       或「失控過長」的離譜結果，落在容忍區間就放行。
    """
    if not isinstance(content, dict):
        raise ValueError("FB 內容格式錯誤：AI 回傳不是 JSON 物件")

    article = str(content.get("article", "")).strip()
    if not article:
        raise ValueError("FB 內容格式錯誤：缺少 article")

    # 字數粗估：拿掉所有空白字元再算長度
    char_count = len("".join(article.split()))
    if char_count < FB_ARTICLE_MIN:
        raise ValueError(
            f"FB 內容格式錯誤：文章太短（{char_count} 字 < {FB_ARTICLE_MIN}）"
        )
    if char_count > FB_ARTICLE_MAX:
        # 過長不直接 fail（內容可能很好），記 warning 讓使用者知道
        logger.warning("FB 文章偏長：%d 字（建議 ≤ %d）", char_count, FB_ARTICLE_MAX)
    content["article"] = article

    cover = content.get("cover")
    if not isinstance(cover, dict) or not str(cover.get("title", "")).strip():
        raise ValueError("FB 內容格式錯誤：cover 必須是物件且含 title")
    # 正規化 cover 欄位，缺的補空字串，避免渲染模板取值出錯
    content["cover"] = {
        "tag": str(cover.get("tag", "")).strip(),
        "title": str(cover["title"]).strip(),
        "subtitle": str(cover.get("subtitle", "")).strip(),
    }

    content["discussion_question"] = str(content.get("discussion_question", "")).strip()

    return content


def generate_facebook_content(
    topic: str,
    style_hint: str | None = None,
    research_context: str | None = None,
) -> dict[str, Any]:
    """從題目產生 Facebook 貼文內容（文章本文 + 封面）。

    Args:
        topic: 題目（例：「假讀書」）
        style_hint: 可選的開場風格覆寫；不給就隨機挑
        research_context: 可選的深度研究報告（與 Threads 共用同一份）

    Returns:
        dict，含 "article"（文章本文）、"cover"（封面 dict）、"discussion_question"
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required. Set it in .env")

    style = style_hint or random.choice(OPENING_STYLES)
    has_research = "有研究報告" if research_context else "無研究報告"
    logger.info(
        "呼叫 OpenRouter（FB）：model=%s, style=%s, %s",
        OPENROUTER_MODEL,
        style,
        has_research,
    )

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": _build_system_prompt(style)},
            {"role": "user", "content": _build_user_prompt(topic, research_context)},
        ],
        temperature=0.85,
        frequency_penalty=0.4,
        presence_penalty=0.3,
        # ⚠️ FB 是單篇文章，比 Threads 的多 slide 短，1500 tokens 足夠
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()
    logger.debug("FB API 回應長度：%d 字元", len(text))

    try:
        content = json.loads(_clean_model_response(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"FB 內容格式錯誤：AI 回傳無法解析成 JSON。{exc}") from exc

    content = _validate_facebook_payload(content)
    logger.info(
        "FB 內容產生完成：article=%d字, cover.title=%s",
        len("".join(content["article"].split())),
        content["cover"]["title"],
    )
    return content

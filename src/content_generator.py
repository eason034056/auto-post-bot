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
    # 💡 下面 2 種是「知識價值型」開場，跟上面 7 種「情緒勾子型」並列
    #    搭配事實密度高的研究報告時，用這兩種能把「情緒文」變「知識文」
    "數據揭露型",       # 「你知道嗎？[研究數據]。但更關鍵的是背後機制…」→ 先給知識，再給勾子
    "機制解釋型",       # 「為什麼孩子會 [現象]？研究發現：[機制]…」→ 建立知識框架而非焦慮框架
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

# ── 內容結構池（Phase 3：破除千篇一律）──────────────────────
# 💡 之前只有「六段結構」一種骨架，即使開場換 7 種，讀起來還是像同個人寫的。
# 擴充成 4 種結構後，開場 × 結構 = 28 種變化，大幅降低樣板感。
# ⚠️ 每個結構的 flow 會直接注入 prompt 當 content_strategy，也會出現在 log／前端，
#    所以命名要維持「動詞開頭、6 字內」風格跟原本對齊。
CONTENT_STRUCTURES: list[dict[str, Any]] = [
    {
        "name": "Threads 爆文六段結構",
        "flow": ["好奇開頭", "強烈難題", "結果預告", "對話還原", "規律總結", "引導思考"],
        "description": "經典爆文骨架：hook → 痛點 → 預告反轉 → 對話還原 → 規律 → CTA",
    },
    {
        "name": "反差敘事結構",
        "flow": ["驚人結果", "時光倒流", "關鍵轉折", "具體做法", "收束金句", "引導留言"],
        "description": "倒敘：先拋結果再回溯原因，適合有戲劇性轉變的個案",
    },
    {
        "name": "Q&A 拆解結構",
        "flow": ["家長真實提問", "常見錯誤答案", "正確思路", "案例佐證", "行動邀請"],
        "description": "Q&A 形式：直接回應家長疑問，破除錯誤認知，適合觀念型主題",
    },
    {
        "name": "類型對照結構",
        "flow": ["三種類型速寫", "各自盲點", "共通解法", "真實案例", "邀請對號入座"],
        "description": "把家長／學生分 2-3 型各自描述，讀者會主動對號入座增加參與感",
    },
]

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


def _build_system_prompt(style_hint: str, structure: dict[str, Any]) -> str:
    # 💡 把選中的結構 flow 渲染成編號列表，注入 prompt 替代硬寫死的「六段結構」
    structure_name = structure["name"]
    structure_desc = structure.get("description", "")
    flow_lines = "\n".join(
        f"{i}. **{step}**" for i, step in enumerate(structure["flow"], start=1)
    )
    # JSON schema 用的 content_strategy 範例也要跟著換，不然模型會抄舊的
    strategy_json = json.dumps(structure["flow"], ensure_ascii=False)

    return f"""你是「青椒老師」，清大交大家教老師團隊的社群夥伴，在 Threads 分享國中學習方法給家長。語氣是「LINE 群組跟熟識家長聊天」，不是教育專家訓話。

## 寫作原則（違反任一條 = 失敗）

1. **口語第一**：台灣繁體中文口語，禁書面語／學術語／報告體；語助詞自然出現，不要刻意塞
2. **節奏破碎**：句長短長交錯，連三句差不多長就重寫；用停頓、問句帶節奏
3. **段落跳躍**：用「欸你知道嗎」「後來我發現」「結果呢」這種口語，不要制式轉折詞
4. **案例具體**：「那天他居然自己打開課本」打贏「孩子有進步」十條街
5. **結尾不空**：禁「一起加油」「別猶豫」這種空話，丟具體問題引留言
6. **寫得簡潔**：能用 10 字講完就不用 20 字；每張 slide 只講一件事

## 禁抽象形容詞（機器感主因）

AI 味最明顯的特徵就是形容詞堆砌。**禁止**使用下列空話類形容詞：
「關鍵的、重要的、有效的、顯著的、明顯的、大幅、極大、革命性、突破性、全方位、全面、卓越、優異、極致」

**每個好處要用具體畫面取代抽象形容**：
- ❌「成績明顯提升」→ ✅「月考數學從 38 分爬到 67 分」
- ❌「學習效率變高」→ ✅「以前一小時只寫兩題，現在半小時寫完一整張」
- ❌「孩子變得更自律」→ ✅「晚上十點我去看，他自己還在訂正」

看不到畫面就是 AI 寫的，要讓家長讀到能腦補出場景。

## AI 味特徵詞（看到任何一類就是 AI 文）

以下每類都是 AI 生成的招牌。**連『同類表達』也不行**——避開「首先」不代表能用「先來說」，避開「此外」不代表能用「另外還有」。要用熟識家長會用的口語整個換掉：

{_BANNED_BLOCK}

## 格式硬規則
- **禁 emoji**：圖像渲染無 emoji 字型，一律純文字
- **JSON only**：輸出純 JSON object，禁 markdown fence、禁解釋文字

## 今日開場：**{style_hint}**

9 種開場公式（用在 hook 第一句製造點擊動機）：

情緒勾子型（適合情緒共鳴優先的主題）：
- **共識否定型**：「大家都覺得 [觀念]…」→ 建錨再打碎
- **場景共鳴型**：「你家孩子是不是也 [行為]？」→ 第二人稱觸發共鳴
- **禁止誘惑型**：「千萬不要 [動作]…」→ 越禁越想看
- **數據震撼型**：「[數字] 的國中生 [事實]」→ 數字建權威
- **結果前置型**：「[震驚結果]，只因為 [微小原因]」→ 好奇驅動
- **權威顛覆型**：「[權威] 說了一句讓家長沉默的話…」→ 懸念
- **故事開場**：第一句直接切入真實案例的具體場景

知識價值型（適合有研究/方法為主的主題，傳遞「這帳號有料」）：
- **數據揭露型**：「你知道嗎？[具體研究數據或官方統計]。但更關鍵的是背後的機制…」→ 第一句就給家長有用資訊，再用機制勾住
- **機制解釋型**：「為什麼孩子會 [現象]？[學習科學 / 發展心理] 研究發現：[機制]。理解這點後，只要做一件事就能改變結果…」→ 從「為什麼」切入，建立知識框架而非焦慮框架

**開場選擇指引**：若研究報告以事實 / 方法 / 具名專家為主（情緒素材少），**優先選用「數據揭露型」或「機制解釋型」**，讓家長第一眼就感覺「這裡提供知識」而非「這裡製造焦慮」。

## 今日結構：**{structure_name}**

> {structure_desc}

請按下列段落流程展開（依序對應 slide，不要跳順序）：

{flow_lines}

## 版位對應
- `slides[0]` = `title`（**主標每行 ≤ 10 字**，可拆 1-2 行製造認知衝突；**最後一行是副標** ≤ 15 字補述或 call-to-value；共 2-3 行用 `\n` 分隔。**嚴禁**主標單行超過 10 字，否則圖片會換行變醜）
- 痛點段用 `bullet_list`
- 中段至少一張 `summary` 或 `numbered` 先預告結果
- 有「對話／案例／轉折」類段落用 `case_study`
- 有**醒目數據**（如成績變化、比例、時數）時用 `data` 單張放大震撼
- 有**二元對立**論述（假 vs 真、錯 vs 對、以前 vs 現在）時用 `comparison`
- 倒數第二張用 `summary` 收金句
- **最後一張固定 `cta`**

## 新版型使用時機（重要）
**`data`** — 全篇最多 1 張，用來放「一看就記得」的關鍵數據。例：
- 單數據（推薦）：`stats: [{{"value": "62 → 89", "label": "學生月考從 62 分提升到 89 分"}}]`
- 多數據（並列）：`stats: [{{"value": "3 hr", "label": "..."}}, {{"value": "40 min", "label": "..."}}]`
- `value` 要短（≤ 6 字符，含數字+單位），`label` 簡述情境（≤ 20 字）

**`comparison`** — 全篇最多 1 張，用來做二元對照。例：
- `left_label: "假讀書"`，`right_label: "真讀書"`
- `rows: [{{"left": "眼睛從頭掃到尾", "right": "讀一段停一段"}}, ...]`
- 每個 left/right cell ≤ 12 字；rows 3-5 列最佳

## 章節標籤 tag（每張除 cta 外都必填）
`tag` 是小標籤（出現在圖片頂端 eyebrow 區），**2-6 字**，用來標示章節屬性。可以：
- **單中文**：「常見誤區」「方法」「問題」「學習心法」
- **中英並陳**（推薦，更精緻）：「方法 / METHOD」「案例 / CASE」「金句 / TAKEAWAY」「觀點 / INSIGHT」
tag 要與該 slide 類型吻合：numbered → 方法類、bullet_list → 問題/誤區類、case_study → 案例類、summary → 金句類、title → 主題領域類。

## CTA 原則（輕帶不強推）
用「忙／沒時間」當台階，**不能暗示家長不會教**。收尾尊重：「想自己來或想找人幫忙都行」。

## JSON Schema（嚴格遵守）

{{
  "hook": "Threads post text（不是 slide 文字）。3 段式結構（視覺停留點 → 情境具體化 → 留白勾住），總長 120-200 字；至少含 1 個具體數字、1 個具名來源、1 個具體畫面；結尾留勾不給答案",
  "structure_name": "{structure_name}",
  "content_strategy": {strategy_json},
  "discussion_question": "**at most 2 句**，口語、具體、容易留言",
  "slides": [
    {{"type": "title", "tag": "學科領域 / 心法標籤", "content": "主標 2 行\\n副標 1 行（共 2-3 行，用 \\n 換行）"}},
    {{"type": "bullet_list", "tag": "常見誤區", "title": "...", "items": ["..."], "footer": "可選"}},
    {{"type": "numbered", "tag": "方法 / METHOD", "number": 1, "title": "...", "content": "...", "example": "不加『例如：』前綴"}},
    {{"type": "data", "tag": "數據 / DATA", "stats": [{{"value": "62 → 89", "label": "情境描述 ≤ 20 字"}}], "source": "可選資料源"}},
    {{"type": "comparison", "tag": "對比 / COMPARE", "title": "假讀書 vs 真讀書", "left_label": "假讀書", "right_label": "真讀書", "rows": [{{"left": "≤ 12 字", "right": "≤ 12 字"}}]}},
    {{"type": "case_study", "tag": "案例 / CASE", "title": "...", "problem": "具體場景", "solution": "調整方法", "result": "具體細節"}},
    {{"type": "summary", "tag": "金句 / TAKEAWAY", "content": "金句\\n可換行"}},
    {{"type": "cta", "content": "青椒老師專業家教服務\\n服務地區: 新竹 | 台北\\n專業領域: 國高中小家教媒合\\n點擊留言連結直接加入官方Line好友"}}
  ]
}}

請產出 **at most 10 張** slides（最少 6 張），整體要有節奏起伏，不是從頭到尾一個語氣。"""


def _build_user_prompt(topic: str, research_context: str | None = None) -> str:
    base = f"""請為以下題目撰寫一篇完整的 Threads 圖文貼文內容：

**題目**：{topic}"""

    if research_context:
        base += f"""

以下是針對「{topic}」的實證導向深度研究報告（含事實基礎 / 觀點光譜 / 實證方法 / 引用來源）：
========================================
{research_context}
========================================

**素材使用原則**（嚴格執行，違反任一條等於沒用上研究）：

事實與來源：
- hook 優先用：**量化事實** / **有研究支持的洞察** / **具名專家的反直覺結論**（禁用憑空推論）
- 每個事實主張需在內文帶出來源類型，例：「研究顯示…」「108 課綱明訂…」「親子天下訪談某國中老師指出…」
- 若研究報告沒提到的數字，**不要自己編**；寧可不說數字也不要捏造

人物與案例：
- case_study 使用：具名專家案例 / 學術個案 / 具名教師觀察
- **禁用**：「一位家長分享」「有位媽媽說」「很多家長都…」這類無法驗證的匿名敘述
- 極端個案**絕對不得**敘述為普遍現象

金句與論點：
- title 金句從「最具操作價值」的洞察提煉（讀完能立刻做點什麼），不是「最反直覺」的獵奇
- summary 金句必須是「結論 + 機制」（不只講結論，還講為什麼）
- bullet_list 用量化事實陳述（比例 / 步驟 / 條件），不用家長抱怨口吻的擴張描述

開場公式選擇：
- 若研究報告以事實 / 方法為主（情緒素材少）→ 優先用「數據揭露型」或「機制解釋型」開場
- 讓家長看完 hook 第一句就覺得「我學到東西了」，而不是「我被戳到了」

### Hook（post text）結構規範（Threads 貼文文字本身）

Hook 是 Threads 上家長最先看到的文字，**前 2 行決定是否繼續看**。按下列 3 層結構撰寫：

1. **第 1 行（≤ 40 字）— 視覺停留點**
   必須是下列之一：
   - 具體數字 / 比例（例：「教育部 2023 年調查：國中生每天專注讀書不到 38 分鐘」）
   - 具名權威的反轉觀點（例：「親子天下訪談 12 位國中老師，一半都不建議家長陪讀」）
   - 立即好奇題（有明確答案、不是空泛疑問）
   - 機制開關（例：「孩子假讀書不是懶，是大腦的保護機制啟動了」）

2. **第 2-3 行（40-120 字）— 情境具體化**
   把第 1 行的抽象點，用一個具體畫面或具名案例落地。
   禁：「很多家長都有這種困擾」「這真的讓人很頭痛」這類擴張敘述。

3. **第 4-5 行（120-200 字）— 留白勾住**
   暗示答案存在但不說破，引導滑到下一張 slide。
   禁：直接給答案（答案放 slides 裡）、自我介紹、業配感 CTA。

**Hook 禁區**：
- 籠統抱怨（「家長都很煩惱」「真的很難教」）
- 空洞問句（「你是不是也覺得很累？」→ 除非後面立刻有具體畫面）
- 自我介紹（「我是青椒老師」— 人設靠內容自然流露，不明說）
- 結尾 CTA（「快私訊我」等 CTA 留給置頂留言）

**Hook 必須包含（檢查清單）**：
- [ ] 至少 1 個具體數字 / 比例 / 時間
- [ ] 至少 1 個具名來源（研究 / 專家 / 教師 / 官方文件）
- [ ] 至少 1 個具體畫面或情境（不是純抽象概念）
- [ ] 結尾有勾子（讓人想滑下一張）"""
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
    # 💡 每次隨機挑一種結構，跟開場 style 正交，避免每篇骨架都一樣
    structure = random.choice(CONTENT_STRUCTURES)
    has_research = "有研究報告" if research_context else "無研究報告"
    logger.info(
        "呼叫 OpenRouter：model=%s, style=%s, structure=%s, %s",
        OPENROUTER_MODEL,
        style,
        structure["name"],
        has_research,
    )

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": _build_system_prompt(style, structure)},
            {"role": "user", "content": _build_user_prompt(topic, research_context)},
        ],
        temperature=0.85,
        # 💡 frequency_penalty: 壓制重複出現的 token，降低「贅詞／套話循環」
        frequency_penalty=0.4,
        # 💡 presence_penalty: 鼓勵引入新詞彙，打破同質化語氣
        presence_penalty=0.3,
        # ⚠️ max_tokens 是硬截斷（不是軟性精簡），防止長度失控
        # Claude Sonnet 4.6 預設會寫到停不下來；2500 tokens 約 = 6-10 張 slide 的上限
        max_tokens=2500,
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

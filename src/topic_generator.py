"""AI 題目產生器：為青椒家教 Threads 貼文自動產生題目。

設計三層機制（解決「題目沒創意」問題）：
- A. 主題 × 角度雙維抽樣：把 TOPIC_CATEGORIES（What）與 TOPIC_ANGLES（How）正交組合
- B. 批量生成 + 二階篩選：一次產 N 個候選，再用 rubric 挑最有張力的 1 個
- F. 即時社會信號：用 Perplexity 抓本週教育圈熱點，注入發想 prompt
"""
import logging
from datetime import datetime

from openai import OpenAI

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    PERPLEXITY_MODEL,
)
# 💡 重用 researcher 的 Perplexity 呼叫器，避免重寫 429 重試 / citations 解析
from .researcher import _call_perplexity, is_research_available

logger = logging.getLogger(__name__)

# === 主題類別池（What 維度）─────────────────────────────────────
# 提供「題目可以講什麼」的方向，不直接拿來當題目
TOPIC_CATEGORIES = [
    # 讀書方法與效率
    "讀書方法與效率",
    "番茄鐘、專注力訓練",
    "筆記法（康乃爾、心智圖）",
    "費曼學習法、主動回憶",
    "間隔重複、記憶曲線",
    # 時間管理與拖延
    "時間管理與拖延",
    "拖延心理、如何開始",
    "時間塊、優先級排序",
    "早起讀書、晨間習慣",
    "週末 vs 平日讀書節奏",
    # 考試準備與心態
    "考試準備與心態",
    "考前焦慮、壓力調適",
    "考試技巧、答題策略",
    "粗心防治、檢查習慣",
    "考後檢討、錯題分析",
    # 親子溝通與陪伴
    "親子溝通與陪伴",
    "親子衝突、情緒處理",
    "對話技巧、傾聽與提問",
    "陪伴品質、有效陪伴",
    "放手界限、自主 vs 督促",
    # 學習動機與習慣
    "學習動機與習慣",
    "內在動機、外在獎勵",
    "習慣養成、環境設計",
    "假讀書、表面努力",
    "沒自信、自我否定",
    # 國中常見學習困擾
    "國中常見學習困擾",
    "分心、手機誘惑",
    "科目偏食、弱科逃避",
    "被動學習、等老師教",
    "補習多卻沒進步",
    # 學科學習技巧
    "學科學習技巧",
    "數學解題、觀念 vs 刷題",
    "英文單字、閱讀、聽力",
    "國文閱讀、作文",
    "理化、社會科記憶法",
    # 考前衝刺與複習
    "考前衝刺與複習",
    "複習計畫、時間分配",
    "錯題本、弱點攻克",
    "考前作息、睡眠與飲食",
    # 升學與生涯
    "會考準備、志願選填",
    "高中職選擇、生涯探索",
    "補習取捨、自學能力",
    # 其他
    "3C 使用、螢幕時間",
    "同儕壓力、比較心態",
    "師生關係、請教老師",
]


# === 切入角度池（How 維度）─────────────────────────────────────
# ⚠️ 同一個主題搭不同角度會產出完全不同的題目。
#    例：主題「假讀書」× 角度「反直覺揭露」→「為什麼資優生反而更容易假讀書？」
#       主題「假讀書」× 角度「具名個案敘事」→「一位清大學長：我國中時的假讀書其實救了我」
TOPIC_ANGLES = [
    {
        "name": "反直覺揭露",
        "desc": "顛覆家長預設或常識，揭露「其實…」的真相",
        "examples": "為什麼努力讀書反而成績更差？／資優生最常做的『錯』事",
    },
    {
        "name": "具名個案敘事",
        "desc": "用具名專家、學生、老師的真實故事或觀察起手",
        "examples": "一位清大學長回顧他的『假讀書』時期／某國中老師上課悄悄做的一件事",
    },
    {
        "name": "數據拆解",
        "desc": "用具體數據或研究結果作為題目核心",
        "examples": "38% 的國中生每天讀書不到 1 小時，但不是因為懶／腦科學研究：14 歲大腦正在發生這件事",
    },
    {
        "name": "禁忌指令",
        "desc": "違反主流家長行為的反向、看似不負責任的建議",
        "examples": "拜託，不要再陪孩子讀書了／考前一週請允許孩子大睡",
    },
    {
        "name": "冷門事實",
        "desc": "鮮為人知但實用的觀察或現象",
        "examples": "國中生忘東忘西不是粗心，是大腦正在重組／段考成績其實預測不了會考成績",
    },
    {
        "name": "跨領域類比",
        "desc": "用非教育領域的概念類比學習現象",
        "examples": "孩子讀書像在玩股票：你正在教他追高殺低／家長督促像 GPS：報太多反而迷路",
    },
    {
        "name": "場景時刻特寫",
        "desc": "從一個具體時刻、畫面、3 秒鐘切入",
        "examples": "晚上 11 點，書桌前的這個畫面決定了明天的成績／考卷發回來那 3 秒",
    },
    {
        "name": "對比反差",
        "desc": "兩個情境、角色、時期或做法的強烈對比",
        "examples": "同樣補習，為什麼有人逆襲有人原地踏步？／兩種家長的對話差 1 句話，孩子差 20 分",
    },
]


# === 候選生成參數 ──────────────────────────────────────────────
NUM_CANDIDATES = 10  # 一次批量生成多少個候選題目
SIGNAL_TIMEOUT = 60.0  # Perplexity 即時信號 timeout（秒）
SIGNAL_MAX_TOKENS = 1500


# ── 即時社會信號（F）──────────────────────────────────────────


def fetch_current_signals(date: datetime) -> str | None:
    """[F] 用 Perplexity sonar-pro 抓本週台灣國中教育圈熱點。

    💡 失敗時回 None，不阻塞題目生成；只是會少一個發想維度。
    ⚠️ 用 sonar-pro 而非 sonar-deep-research：題目發想需要的是訊號廣度
       而非分析深度，sonar-pro 30 秒搞定就夠了。
    """
    if not is_research_available():
        logger.info("研究功能不可用，跳過即時信號階段")
        return None

    date_str = date.strftime("%Y 年 %m 月")
    query = f"""請搜尋台灣國中教育領域，最近 7-14 天（{date_str} 期間）的熱門話題與動態，包含：

1. 教育新聞 / 政策變動 / 爭議事件（教育部、國教院、各地教育局公告）
2. 家長熱議的話題（從專業媒體報導，**非匿名論壇情緒貼文**）
3. 學校 / 老師 / 學生群體中的新現象、新做法、新挑戰

要求：
- 列出 **5-8 個** 具體事件或話題
- 每個附 1 行摘要：「[日期] [事件] [核心爭點或現象]」
- 優先來源：教育部 / 國教院 / 親子天下 / 國語日報 / 聯合新聞網教育版 / 專業教育媒體
- **排除**：商業廣告、補習班置入文、Dcard/PTT 匿名情緒貼文、超過 14 天的舊聞

範例格式：
- [113.04.15] 113 會考英文題型新增聽力比重，補教界與第一線老師意見分歧
- [113.04.10] 親子天下訪談：12 位國中老師對 AI 工具進入課堂的看法
- [113.04.18] 教育部公告 113 學年度國中課程實施要點，新增...

請直接列出，繁體中文。"""

    system_prompt = (
        "你是台灣教育議題編輯，專門整理國中教育最新動態。"
        "嚴格要求引用來源與日期，排除無查核基礎的論壇貼文。"
    )

    try:
        report = _call_perplexity(
            model=PERPLEXITY_MODEL,
            system_prompt=system_prompt,
            query=query,
            max_tokens=SIGNAL_MAX_TOKENS,
            timeout=SIGNAL_TIMEOUT,
        )
        if report:
            logger.info("即時信號抓取完成（%d 字）", len(report))
        return report
    except Exception as e:  # noqa: BLE001 — 任何異常都不該阻塞題目生成
        logger.warning("即時信號抓取失敗（不影響流程）：%s", e)
        return None


# ── Prompt 建構（A + B + F）──────────────────────────────────


def _render_angles_block() -> str:
    """渲染 TOPIC_ANGLES 為 prompt 區塊。"""
    lines = []
    for angle in TOPIC_ANGLES:
        lines.append(
            f"- **{angle['name']}**：{angle['desc']}\n  範例：{angle['examples']}"
        )
    return "\n".join(lines)


def _get_seasonal_hints(date: datetime) -> str:
    """日期/月份/週幾的學期節慶情境提示。"""
    month = date.month
    season_hints: list[str] = []
    if month == 1:
        season_hints.extend(["寒假、學測、寒假作業", "新年新希望、學期目標"])
    elif month == 2:
        season_hints.extend(["開學準備、收心", "寒假收尾、新學期適應"])
    elif month == 3:
        season_hints.extend(["開學季、新學期適應", "第一次小考、學習節奏"])
    elif month == 4:
        season_hints.extend(["第一次段考前後", "期中考衝刺", "春假、連假讀書"])
    elif month == 5:
        season_hints.extend(["會考、段考、期末考", "考前衝刺", "志願選填"])
    elif month == 6:
        season_hints.extend(["期末考、暑假前", "會考放榜", "暑假規劃"])
    elif month == 7:
        season_hints.extend(["暑假、自主學習", "暑期銜接", "補強弱科"])
    elif month == 8:
        season_hints.extend(["暑假尾聲、收心", "開學前準備", "新學年規劃"])
    elif month == 9:
        season_hints.extend(["新學年、開學適應", "第一次段考準備", "新班級新老師"])
    elif month == 10:
        season_hints.extend(["第一次段考", "期中考前", "秋假、連假"])
    elif month == 11:
        season_hints.extend(["第二次段考", "期中檢討", "期末複習啟動"])
    elif month == 12:
        season_hints.extend(["第二次段考、期末複習", "寒假前衝刺", "年末回顧"])

    # 💡 過去這裡有 weekday_hints 把每個週幾都硬綁一組關鍵字（週一=收心、週三=小週末…），
    #    跟 TOPIC_ANGLES 的發散設計互相打架，且大多是腦補不是真實規律，已完全移除。
    #    日期/週幾仍會在 prompt 顯示，但讓模型自行判斷意義，不再注入預設 frame。
    return "、".join(season_hints) if season_hints else "一般學習與親子議題"


def _get_rotated_categories(date: datetime, sample_size: int = 16) -> str:
    """日輪換主題類別池起點，避免連續幾天同類主題。"""
    day_of_year = (date - datetime(date.year, 1, 1)).days
    start = day_of_year % len(TOPIC_CATEGORIES)
    rotated = TOPIC_CATEGORIES[start:] + TOPIC_CATEGORIES[:start]
    return "、".join(rotated[:sample_size])


def _build_candidates_prompt(date: datetime, signals: str | None) -> str:
    """[A+B+F] 組裝批量候選題目的發想 prompt。"""
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date.weekday()]
    month, day = date.month, date.day
    season_hints = _get_seasonal_hints(date)
    categories_sample = _get_rotated_categories(date)
    angles_block = _render_angles_block()

    if signals:
        signals_block = f"""## 本週教育圈即時動態（請務必從中發想至少 3 個與當前時事連結的題目）

{signals}
"""
    else:
        signals_block = "## 本週教育圈即時動態\n（暫無即時信號，請從常設主題與角度發揮）\n"

    return f"""你是青椒家教（清大、交大家教老師團隊）的內容企劃。請為今日 Threads 圖文貼文發想 **{NUM_CANDIDATES} 個** 候選題目。

## 目標客群
台灣國中家長：關心孩子學習成效、讀書方法、親子互動。

## 今日情境
- 日期：{month} 月 {day} 日（週{weekday}）
- 學期 / 節慶情境：{season_hints}

{signals_block}
## 主題類別池（What — 提供方向，**不限於此**；避免每個題目選同類）
{categories_sample}

## 切入角度池（How — **每個題目必須選用一種角度**）

{angles_block}

**{NUM_CANDIDATES} 個題目至少需用到 6 種以上不同角度。** 同一角度最多重複使用 2 次。

## 題目品質硬規範

每個題目必須通過下列三項檢查（任一未通過 = 該題作廢）：

1. **「咦？」反應檢測**：讀者讀到題目，會不會產生「咦？」「真的嗎？」「我從沒這樣想過」的反應？如果只是「對啊我也想知道」這種平庸共鳴 → 不夠
2. **不老梗檢測**：過去 5 年親子天下、媽咪拜、各家媽媽社團寫過上百遍的大眾化題目 → 直接淘汰。例：「如何幫孩子建立讀書習慣」「考前焦慮怎麼辦」「親子溝通技巧」這種無角度的題目
3. **具體畫面檢測**：題目本身有畫面感嗎？「讀書方法」「時間管理」這種抽象詞 → 淘汰；「為什麼晚上 11 點的書桌前那個畫面，決定了明天的成績」→ 過關

## 格式自由（突破舊版 3-8 字短名詞限制）

題目可以是：
- 反問句：「為什麼資優生反而更容易假讀書？」
- 數據句：「38% 的國中生每天讀書不到 1 小時，但不是因為懶」
- 具名引述：「一位清大學長：我國中時的『假讀書』其實救了我」
- 場景特寫：「考卷發回來那 3 秒，決定了孩子下次的成績」
- 反向指令：「拜託，不要再陪孩子讀書了」
- 對比句：「兩種家長的對話差 1 句話，孩子差 20 分」
- 短名詞（仍可，但要有張力）：「假讀書」「拖延腦」

## 內容可發揮性
每個題目都需能延伸成 8-10 張圖的實用內容（不是純情緒共鳴的標題黨）

## 輸出格式（嚴格遵守）

請輸出 **{NUM_CANDIDATES} 個** 題目，每行一個，格式：
```
[角度名稱] | [題目]
```

範例：
反直覺揭露 | 為什麼資優生反而更容易假讀書？
具名個案敘事 | 一位清大學長：我國中時的『假讀書』其實救了我
數據拆解 | 38% 的國中生每天讀書不到 1 小時，但研究指向另一個原因

不要編號、不要解釋、不要任何結尾說明，只回傳 {NUM_CANDIDATES} 行「角度 | 題目」。"""


# ── 批量生成 + 二階篩選（B）─────────────────────────────────


def _parse_candidate_line(line: str) -> dict[str, str] | None:
    """解析一行 `[角度] | [題目]` 格式。"""
    line = line.strip()
    if not line:
        return None
    # 移除可能的編號 / 項目符號前綴
    for prefix in ("- ", "* ", "· "):
        if line.startswith(prefix):
            line = line[len(prefix):].strip()
    # 移除「1. 」這種編號
    if len(line) >= 2 and line[0].isdigit() and line[1] in ".．、":
        line = line[2:].strip()

    # ⚠️ AI 寫中文時常把分隔符吐成全形「｜」而非半形「|」，兩者都要接
    sep = "|" if "|" in line else ("｜" if "｜" in line else None)
    if sep:
        angle, topic = (s.strip() for s in line.split(sep, 1))
    else:
        angle, topic = "", line

    # 清掉引號類字元
    for ch in ('"', "'", "「", "」"):
        topic = topic.replace(ch, "")
    topic = topic.strip()

    if not topic:
        return None
    return {"angle": angle, "topic": topic}


def _generate_candidates(prompt: str) -> list[dict[str, str]]:
    """[B step 1] 一次產 NUM_CANDIDATES 個候選題目。

    💡 高溫 + 高 frequency_penalty：強迫模型發散思考，避免 10 個題目都長類似。
    """
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,           # 創意需要溫度
        frequency_penalty=0.6,     # 強壓重複用語
        presence_penalty=0.4,      # 鼓勵引入新詞彙
        max_tokens=1200,           # 10 題 × 平均 80 字 + 角度標籤
    )
    text = (response.choices[0].message.content or "").strip()
    candidates: list[dict[str, str]] = []
    for line in text.split("\n"):
        parsed = _parse_candidate_line(line)
        if parsed:
            candidates.append(parsed)
    logger.info("生成 %d 個候選題目", len(candidates))
    if logger.isEnabledFor(logging.DEBUG):
        for i, c in enumerate(candidates, 1):
            logger.debug("  候選 %d: [%s] %s", i, c["angle"] or "未標註", c["topic"])
    return candidates


def _select_best_topic(candidates: list[dict[str, str]], signals: str | None) -> str:
    """[B step 2] 用 5 項評分標準從候選中挑出最佳題目。

    💡 評分而非自由選擇 → 強迫模型有依據，避免又選回平庸題目。
    """
    if len(candidates) == 1:
        return candidates[0]["topic"]

    candidate_block = "\n".join(
        f"{i + 1}. [{c['angle'] or '未標註'}] {c['topic']}"
        for i, c in enumerate(candidates)
    )

    signals_context = (
        "（本週確實有可參考的教育圈動態，請評分時把『時事連結』納入考量。）"
        if signals
        else "（本週無即時信號可用，『時事連結』一項給中性 3 分。）"
    )

    prompt = f"""你是青椒家教 Threads 內容主編。下面有 {len(candidates)} 個候選題目，請依評分標準挑出最佳的 1 個。

{signals_context}

## 候選題目

{candidate_block}

## 評分標準（每項 1-5 分，總分 25 分）

1. **認知衝擊**：讀者會不會產生「咦？」「真的嗎？」反應？挑戰預設或揭露未知 → 4-5 分；只是平庸共鳴 → 1-2 分
2. **具體畫面**：題目本身有畫面感、能腦補出場景 → 4-5 分；抽象口號 → 1-2 分
3. **不老梗**：過去 5 年親子媒體沒寫爛的角度 → 4-5 分；大眾化主題 → 1-2 分
4. **可發揮性**：能延伸成 8-10 張圖實用內容（不是純標題黨）
5. **時事連結**：呼應本週教育圈動態？

## 輸出格式

**只回傳：題目文字本身**（不含角度標籤、編號、解釋、評分、引號）

例如，若你選擇「具名個案敘事 | 一位清大學長：我國中時的『假讀書』其實救了我」
你的回傳應該是：
一位清大學長：我國中時的『假讀書』其實救了我

請選出最佳題目："""

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,  # 評選需要穩定，不需要創意
        max_tokens=200,
    )
    selected = (response.choices[0].message.content or "").strip()

    # 清掉可能的引號 / 角度標籤殘留
    for ch in ('"', "'", "「", "」"):
        selected = selected.replace(ch, "")
    if "|" in selected:  # ⚠️ 如果模型沒照指示去掉 [角度] 前綴，就只取 | 後面
        selected = selected.split("|", 1)[1].strip()
    selected = selected.strip()

    if not selected:
        # 退路：回傳第一個候選
        logger.warning("篩選階段未回傳有效題目，使用第一個候選")
        return candidates[0]["topic"]

    return selected


# ── 對外主入口 ────────────────────────────────────────────────


def generate_topic_candidates() -> dict[str, object]:
    """產生候選題目並標出 AI 推薦的最佳題目。

    💡 為什麼拆出這個函式：前端要讓使用者從候選中挑選，需要看到全部候選+AI 推薦；
    CLI 場景則只需要 1 個題目（用 generate_topic() wrapper 取 recommended 即可）。

    流程：[F] 抓即時信號 → [A+B step 1] 主題×角度矩陣批量產 N 候選 → [B step 2] rubric 篩出推薦

    Returns:
        {
            "candidates": [{"angle": str, "topic": str}, ...],
            "recommended": str,  # AI 評分最高的題目文字
            "has_signals": bool, # 是否成功取得即時信號
        }

    Raises:
        ValueError: 未設定 OPENROUTER_API_KEY；或 AI 完全沒回任何候選題目
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 為必填，請在 .env 設定")

    date = datetime.now()

    # [F] 即時社會信號（失敗也不阻塞）
    logger.info("步驟 1/3：抓取本週教育圈即時信號（Perplexity sonar-pro）...")
    signals = fetch_current_signals(date)

    # [A + B step 1] 批量產候選
    logger.info("步驟 2/3：批量產生 %d 個候選題目（model=%s）...", NUM_CANDIDATES, OPENROUTER_MODEL)
    prompt = _build_candidates_prompt(date, signals)
    candidates = _generate_candidates(prompt)

    if not candidates:
        raise ValueError("題目候選生成失敗：AI 沒回任何結果")

    # [B step 2] 二階評分篩選
    if len(candidates) == 1:
        logger.warning("只生成 1 個候選，跳過篩選階段")
        recommended = candidates[0]["topic"]
    else:
        logger.info("步驟 3/3：從 %d 個候選中篩選 AI 推薦題目...", len(candidates))
        recommended = _select_best_topic(candidates, signals)

    logger.info("題目候選產生完成：%d 個候選，AI 推薦『%s』", len(candidates), recommended)
    return {
        "candidates": candidates,
        "recommended": recommended,
        "has_signals": signals is not None,
    }


def generate_topic() -> str:
    """呼叫 AI 產生一個貼文題目（取 AI 推薦的那個）。

    💡 對外保持原介面（main.py / api/main.py 兩個 caller 不需改）；內部委派給
    generate_topic_candidates() 取 recommended，候選清單直接丟掉。
    """
    result = generate_topic_candidates()
    return str(result["recommended"])

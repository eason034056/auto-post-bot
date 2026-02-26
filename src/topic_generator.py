"""AI 題目產生器：為青椒家教 Threads 貼文自動產生題目。"""
import logging
from datetime import datetime

from openai import OpenAI

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

# 題目方向參考，供 AI 發想（每日發文需足夠多樣，避免重複）
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


def _build_topic_prompt(date: datetime) -> str:
    """組裝題目產生 prompt，含日期與節慶情境。"""
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date.weekday()]
    month, day = date.month, date.day

    # 節慶／學期情境（供 AI 參考，每日發文需多樣化）
    season_hints = []
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

    # 週幾微情境（增加每日變化）
    weekday_hints = {
        0: "週一、開學症候群、收心",
        1: "週二、學習節奏、日常習慣",
        2: "週三、小週末、中期檢視",
        3: "週四、週末前、動力維持",
        4: "週五、週末規劃、親子時光",
        5: "週六、週末、自主學習、補習日",
        6: "週日、收假、明日準備",
    }
    season_hints.append(weekday_hints[date.weekday()])

    hint_str = "、".join(season_hints) if season_hints else "一般學習與親子議題"

    # 每日輪換題目方向，避免連續幾天同類
    day_of_year = (date - datetime(date.year, 1, 1)).days
    start = day_of_year % len(TOPIC_CATEGORIES)
    rotated = TOPIC_CATEGORIES[start:] + TOPIC_CATEGORIES[:start]
    categories_sample = "、".join(rotated[:12])  # 每次給 12 個方向參考

    return f"""你是青椒家教（清大、交大家教老師團隊）的社群小編。請為今日 Threads 圖文貼文產出 **一個** 題目。

## 目標客群
國中家長，關心孩子的學習成效、讀書方法、親子互動。

## 今日情境
- 日期：{month} 月 {day} 日（週{weekday}）
- 可參考情境：{hint_str}

## 題目方向（今日可從以下擇一發揮，盡量選不同面向）
{categories_sample}

## 題目要求
1. **簡短**：3–8 個字，例如「假讀書」「孩子拖延怎麼辦」「考前焦慮」
2. **有共鳴**：國中家長會想點進去看
3. **可發揮**：能延伸成 8–10 張圖的實用內容
4. **不重複**：避免常見老梗（如「讀書方法」太籠統），每日換不同角度

## 輸出格式
只回傳題目文字，不要引號、不要編號、不要說明。例如：
假讀書

請直接回傳一個題目："""


def generate_topic() -> str:
    """
    呼叫 AI 產生一個貼文題目。

    Returns:
        題目字串，例如「假讀書」「孩子拖延怎麼辦」

    Raises:
        ValueError: 未設定 OPENROUTER_API_KEY
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 為必填，請在 .env 設定")

    logger.info("呼叫 OpenRouter 產生題目：model=%s", OPENROUTER_MODEL)
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "user", "content": _build_topic_prompt(datetime.now())},
        ],
        temperature=0.9,
        max_tokens=50,
    )

    topic = response.choices[0].message.content.strip()
    # 移除可能的引號或編號
    for char in ('"', "'", "「", "」", "1.", "2.", "-", "·"):
        topic = topic.replace(char, "").strip()
    logger.info("題目產生完成：%s", topic)
    return topic

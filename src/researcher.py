"""Perplexity Sonar Pro 深度研究模組。

透過 OpenRouter 呼叫 Perplexity Sonar Pro，進行即時網路研究，
產出含引用來源的研究報告。約 30 秒即可完成。

用途：在 AI 產生 Threads 貼文前，先研究主題的真實家長討論、
課綱脈絡、情緒觸發點等，讓內容更有深度與共鳴。

移植自 tutor-matching-reels-agent，針對 Threads 貼文情境調整。
"""

import logging
import time

import httpx

from .config import (
    OPENROUTER_API_KEY,
    PERPLEXITY_DEEP_MODEL,
    PERPLEXITY_MODEL,
    RESEARCH_MAX_TOKENS,
    RESEARCH_TIMEOUT,
    RESEARCH_USE_DEEP,
)

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_research_available() -> bool:
    """檢查研究功能是否可用（只需要 OpenRouter API key）。"""
    return bool(OPENROUTER_API_KEY)


# ── 查詢建構 ──────────────────────────────────────────────────


def build_research_query(topic: str) -> str:
    """建構實證導向的深度研究查詢。

    💡 設計原則（對比舊版）：
    - 事實優先於情緒：不預設「家長有什麼情緒」，讓資料說話
    - 來源分級透明：要求每段落標註來源類型
    - 量化優於敘述：能量化的就量化
    - 對立觀點並陳：主流觀點必須搭配反面證據
    - 不預設結論：不假設「有迷思」「有錯誤做法」

    ⚠️ 禁區：不要求 Perplexity 搜社群家長原話（會放大極端少數聲音）。
    改採具名專家、研究、教師的公開發言作為主要來源。
    """
    return f"""主題：「{topic}」— 台灣國中階段（12-15 歲）

請針對這個主題進行深度研究，產出結構化報告，分為三個部分：

## Part 1 — 事實基礎（FACTS）

請回答：
- **客觀現況**：台灣國中生在這個主題上的真實數據？（比例、樣本、年級差異、性別差異若有）
- **發展脈絡**：從認知科學 / 學習心理學 / 青少年發展角度，這現象背後的機制是什麼？
- **課綱脈絡**：108 課綱（十二年國教）對這議題的相關規定、核心素養連結或教學實施指引

要求：
- 每個陳述必須附帶明確來源（研究名稱、作者、年份；或官方文件名稱）
- 若無權威來源請直接寫「暫無明確研究」，**禁止推測或臆造數據**
- 數據優先：能量化的就量化，避免「很多」「常常」「普遍」這類模糊用語

## Part 2 — 觀點光譜（PERSPECTIVES）

請回答：
- **主流觀點**：教育學者 / 學科專家的主流立場是什麼？支持理由與核心論述？
- **少數觀點**：哪些具名研究者或專家提出不同看法？他們的理由與證據？
- **老師視角**：第一線資深教師的實務觀察（優先引用具名教師、學科中心、教師專業社群的公開文章）

要求：
- **禁止**「家長們都說」「很多人認為」「不少家長」這類無法驗證的集合敘述
- 每個觀點須指出：倡議者身份（某某教授/某某國中老師/某某機構）、發表場合（期刊/專書/雜誌專欄）
- 主流觀點若有爭議，必須同時呈現反方論據，不要單方面倡議

## Part 3 — 實證方法（METHODS）

請找出至少 3 種「有研究或實務背書」的具體方法，每種必須包含：
- **方法名稱**（若有學理名詞請使用，例如「間隔學習」「提取練習」「自我解釋」）
- **運作機制**：為什麼這方法有效？（認知科學 / 行為心理 / 動機理論的解釋）
- **適用情境**：什麼類型的孩子、什麼學習階段、什麼科目適合？
- **可能失敗情境**：什麼情況下這方法會無效甚至反效果？
- **具體執行步驟**：家長可以直接照做的 3-5 步操作
- **研究或專家出處**：這方法的背書來源

另外請指出：
- **缺乏證據的流傳說法**：坊間常見但其實沒有研究支持的做法？為什麼缺乏證據？
（這是為了讓家長避開無效方法，不是為了製造「家長有迷思」的焦慮）

## 整體要求（嚴格執行）

**嚴格來源篩選**（排序由高到低優先）：
1. 同儕審查學術期刊（教育心理、認知科學、學習科學）
2. 教育部、國教院、國家教育研究院、學科中心公開資料
3. 專業深度媒體（親子天下、天下雜誌、康健雜誌等的深度報導）
4. 具名學者、臨床心理師、資深教師的專書與公開發言

**禁止來源**（不得作為事實主張的依據）：
- Facebook / Instagram / Dcard / PTT / TikTok 上的家長發文或討論
- 不具名部落格、匿名留言、未經查核的自媒體
- 超過 5 年的非基礎學理資料（學科教學法、教材研究除外）

**語氣規範**：
- 避免情緒化詞語：不寫「焦慮」「挫敗」「無助」「抓狂」等主觀情緒描述
- 避免絕對化：不寫「最有效」「一定要」「絕對不能」「唯一的方法」
- 避免預設結論：不預設「家長做錯了」，只陳述研究 / 專家的客觀觀察

**格式要求**：
- 每段落結尾註明主要來源等級：`[來源：學術研究 / 官方 / 專業媒體 / 具名專家]`
- 繁體中文、專業但可讀的語氣（研究報告風，不是通俗貼文風）

現在請開始研究。"""


# ── API 呼叫 ──────────────────────────────────────────────────


def _append_citations(content: str, citations: list[str]) -> str:
    """將 Perplexity 的引用 URL 附加為腳註。

    Perplexity 回傳的文字中使用 [1], [2] 等標記，但實際 URL
    放在 response 的 citations 陣列中。這裡把它們合併起來，
    讓下游的 content generator 能看到真實來源。
    """
    if not citations:
        return content

    footnotes = "\n\n---\n來源：\n"
    for i, url in enumerate(citations, 1):
        footnotes += f"[{i}] {url}\n"
    return content + footnotes


def _openrouter_post(
    json_body: dict,
    *,
    timeout: float = 120.0,
    max_retries: int = 3,
) -> httpx.Response:
    """POST 到 OpenRouter，帶 429 rate limit 自動重試。

    所有 OpenRouter 呼叫都應走這個函式，確保遇到速率限制時
    會自動 exponential backoff 重試。
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 未設定，請在 .env 中設定")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries + 1):
        response = httpx.post(
            OPENROUTER_CHAT_URL,
            headers=headers,
            json=json_body,
            timeout=timeout,
        )

        # 💡 只有 429 才重試，其他狀態碼直接 raise
        if response.status_code != 429 or attempt >= max_retries:
            response.raise_for_status()
            return response

        # ⚠️ 429 Too Many Requests — exponential backoff
        wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                wait = min(float(retry_after), 30)
            except ValueError:
                pass

        logger.warning(
            "OpenRouter 429 速率限制，%.0f秒後重試（%d/%d）...",
            wait, attempt + 1, max_retries,
        )
        time.sleep(wait)

    # 理論上不會到這裡
    response.raise_for_status()
    return response


# ── 主要研究函式 ──────────────────────────────────────────────


RESEARCH_SYSTEM_PROMPT = """你是獨立的教育研究員，為台灣國中家長撰寫實證導向的教養指南。

## 研究方法論

1. **事實優先於情緒**：先建立客觀事實基礎，再處理主觀經驗；不預設「家長有什麼情緒」或「家長有迷思」，讓資料說話
2. **來源分級透明**：每個主張都必須標註來源等級（學術研究 / 官方資料 / 專業媒體 / 具名專家 / 具名教師）
3. **量化優於敘述**：能量化的就量化，避免「很多家長」「常常」「不少人」這類模糊集合敘述
4. **對立觀點並陳**：主流觀點必須同時提供專家質疑或反面證據，不單方面倡議
5. **不預設結論**：不假設「家長有迷思」「常見錯誤」存在；若研究顯示多數家長做得很好，就如實說
6. **可操作性優先**：每個建議必須說明「運作機制（為什麼有效）」「適用情境」「可能失敗的情境」

## 排除的來源類型（不得作為事實主張的依據）

- Facebook / Instagram / Dcard / PTT / TikTok 等論壇的家長貼文與討論
- 不具名部落格、未經查核的自媒體內容
- 超過 5 年的非基礎學理資料（學科教學法、教材研究不在此限）
- 匿名問答、讀者投書、未經編輯審核的留言

## 優先使用的來源（由高到低）

1. 同儕審查學術期刊（認知科學、教育心理學、學習科學、發展心理學）
2. 教育部、國教院、國家教育研究院、各學科中心的公開資料與課綱文件
3. 專業深度媒體（親子天下、天下雜誌、康健雜誌、翻轉教育等的深度報導，非意見文）
4. 具名臨床心理師、教育學者、大學教授、資深教師的公開著作與發言

## 語氣規範

- 專業但可讀（研究報告風，不是通俗貼文風）
- 避免情緒化詞語：不寫「焦慮」「挫敗」「無助」「抓狂」等主觀情緒描述
- 避免絕對化：不寫「最有效」「一定要」「絕對不能」
- 繁體中文回答
"""


def _extract_content(data: dict) -> tuple[str | None, list[str]]:
    """從 Perplexity/OpenRouter 回應解析出內容與引用列表。

    💡 citations 位置在不同版本 API 會落在不同欄位，所以做多路徑 fallback。
    """
    choice = data["choices"][0]
    content = choice["message"].get("content")
    if content is None:
        return None, []

    # ⚠️ OpenRouter 轉發 Perplexity 時 citations 可能出現在三個位置：
    #    1. data["citations"]                  — Perplexity 原生
    #    2. choice["message"]["citations"]     — OpenRouter 轉發
    #    3. data["search_results"]             — sonar-deep-research 有時用這欄位
    citations = (
        data.get("citations")
        or choice["message"].get("citations")
        or [r.get("url") for r in data.get("search_results", []) if r.get("url")]
        or []
    )
    return content, [c for c in citations if c]


def _call_perplexity(
    *,
    model: str,
    system_prompt: str,
    query: str,
    max_tokens: int,
    timeout: float,
    extra_params: dict | None = None,
) -> str | None:
    """單次呼叫 Perplexity 並回傳附好腳註的研究報告（含 citations）。

    失敗時回傳 None，不 raise —— 交給上層決定要不要 fallback。
    """
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.2,  # 研究需要穩定，調得比寫作低
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
    }
    if extra_params:
        body.update(extra_params)

    try:
        response = _openrouter_post(body, timeout=timeout)
        data = response.json()

        content, citations = _extract_content(data)
        if content is None:
            finish = data["choices"][0].get("finish_reason", "unknown")
            logger.warning("Perplexity 回傳空內容 (model=%s, finish_reason=%s)", model, finish)
            return None

        if citations:
            logger.info("取得 %d 個引用來源", len(citations))
        else:
            logger.info("Perplexity 未回傳引用來源")

        return _append_citations(content, citations)

    except httpx.HTTPStatusError as e:
        # ⚠️ 404 或 400 很可能是模型名不被 OpenRouter 支援 → 值得 fallback
        logger.warning(
            "Perplexity HTTP %d 失敗 (model=%s)：%s",
            e.response.status_code, model, e,
        )
        return None
    except httpx.TimeoutException:
        logger.warning("Perplexity 研究逾時 (model=%s, timeout=%.0fs)", model, timeout)
        return None
    except Exception as e:  # noqa: BLE001 — 我們希望這層吞所有異常，讓 fallback 生效
        logger.warning("Perplexity 研究失敗 (model=%s)：%s", model, e)
        return None


def run_research(topic: str) -> str | None:
    """執行 Perplexity 深度研究，產出實證導向的研究報告。

    Args:
        topic: 貼文主題（例如「假讀書」「考前焦慮」）

    Returns:
        研究報告文字（含引用來源腳註），失敗時回傳 None。

    💡 策略：優先用 sonar-deep-research 做 agentic 多輪研究；若該模型在 OpenRouter
    不可用或超時，自動 fallback 到 sonar-pro，保底產出仍然套用新的 prompt 設計。
    """
    if not is_research_available():
        logger.warning("研究功能不可用：OPENROUTER_API_KEY 未設定")
        return None

    query = build_research_query(topic)

    # 主路徑：sonar-deep-research（agentic 多輪研究，3-5 分鐘）
    if RESEARCH_USE_DEEP:
        logger.info("開始深度研究（sonar-deep-research）：%s", topic)
        report = _call_perplexity(
            model=PERPLEXITY_DEEP_MODEL,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            query=query,
            max_tokens=RESEARCH_MAX_TOKENS,
            timeout=RESEARCH_TIMEOUT,
            # 💡 reasoning_effort 讓模型投入更多內部推理；medium 是品質/成本的平衡點
            extra_params={"reasoning_effort": "medium"},
        )
        if report:
            logger.info("深度研究完成（%d 字）", len(report))
            return report
        logger.warning("sonar-deep-research 失敗，fallback 到 sonar-pro")

    # Fallback / 快速路徑：sonar-pro（單輪，30 秒）
    logger.info("使用 sonar-pro 進行研究：%s", topic)
    report = _call_perplexity(
        model=PERPLEXITY_MODEL,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        query=query,
        max_tokens=4000,
        timeout=120.0,
    )
    if report:
        logger.info("研究完成（%d 字，使用 sonar-pro）", len(report))
    return report

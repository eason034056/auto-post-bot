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

from .config import OPENROUTER_API_KEY, PERPLEXITY_MODEL

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_research_available() -> bool:
    """檢查研究功能是否可用（只需要 OpenRouter API key）。"""
    return bool(OPENROUTER_API_KEY)


# ── 查詢建構 ──────────────────────────────────────────────────


def build_research_query(topic: str) -> str:
    """建構針對 Threads 貼文優化的研究查詢。

    與原版（針對短影音 Reels）不同，這裡聚焦在圖文貼文需要的素材：
    真實家長語言、具體案例、情緒觸發點、可操作的建議。
    """
    return f"""我要為台灣國中生家長撰寫一篇 Threads 圖文貼文，主題是「{topic}」。
這是「青椒家教」（清大、交大家教老師團隊）的品牌帳號，目標是吸引家長互動並私訊。

請幫我研究以下內容：

1. **家長真實聲音**：
   - 在台灣家長論壇（PTT JuniorHigh/BabyMother 板、親子天下、BabyHome）上，家長怎麼討論「{topic}」？
   - 他們用什麼詞彙描述這個困擾？（例如「看到就放棄」「每次都吵架」「不知道怎麼教」）
   - 請盡量引用真實的討論內容或家長原話

2. **108 課綱脈絡**：
   - 「{topic}」在台灣 108 課綱國中階段的定位、教學目標
   - 跟舊課綱比起來有什麼變化讓家長不適應？
   - 具體的教學內容和學習重點

3. **實際案例與解決方案**：
   - 家長或老師分享過的成功案例（具體做了什麼、結果如何）
   - 目前有效的學習方法或策略
   - AI 工具（ChatGPT、Gemini 等）在這個主題上能怎麼幫忙？

4. **情緒觸發點**：
   - 這個主題最容易觸發家長什麼情緒？（焦慮、挫折、愧疚、無助？）
   - 什麼樣的「成功畫面」最能打動家長？（例如「孩子居然自己問了三輪」）
   - 家長最想聽到的一句話是什麼？

5. **常見迷思與錯誤**：
   - 家長在「{topic}」上最常犯的錯誤做法
   - 常見的教育迷思
   - 為什麼這些做法反而有害？

請用繁體中文回答，引用具體來源。語氣像研究報告但不要太學術。"""


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


def run_research(topic: str) -> str | None:
    """執行 Perplexity Sonar Pro 深度研究。

    Args:
        topic: 貼文主題（例如「假讀書」「考前焦慮」）

    Returns:
        研究報告文字（含引用來源腳註），失敗時回傳 None。
    """
    if not is_research_available():
        logger.warning("研究功能不可用：OPENROUTER_API_KEY 未設定")
        return None

    query = build_research_query(topic)
    logger.info("開始 Perplexity 深度研究：%s", topic)

    system_prompt = (
        "你是一個專業的教育研究助手，專門研究台灣國中教育議題。"
        "請用繁體中文回答，盡可能引用具體來源和數據。"
        "如果找到論壇討論或家長原話，請直接引用。"
        "回答要有結構、有深度，但語氣不要太學術。"
    )

    try:
        response = _openrouter_post(
            {
                "model": PERPLEXITY_MODEL,
                "max_tokens": 4000,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
            },
            timeout=120.0,
        )
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        if content is None:
            finish = data["choices"][0].get("finish_reason", "unknown")
            logger.warning("Perplexity 回傳空內容 (finish_reason=%s)", finish)
            return None

        # 💡 OpenRouter 轉發 Perplexity 回應時，citations 位置不固定：
        #    - Perplexity 原生 API: data["citations"]
        #    - OpenRouter 轉發:     data["choices"][0]["message"]["citations"]
        #    兩個位置都檢查，取到哪個用哪個
        citations = (
            data.get("citations")
            or data["choices"][0]["message"].get("citations")
            or []
        )
        if citations:
            logger.info("取得 %d 個引用來源", len(citations))
        else:
            logger.info("Perplexity 未回傳引用來源")

        report = _append_citations(content, citations)
        logger.info("深度研究完成（%d 字）", len(report))
        return report

    except httpx.HTTPStatusError as e:
        logger.warning("Perplexity 研究失敗（HTTP %d）：%s", e.response.status_code, e)
        return None
    except Exception as e:
        logger.warning("Perplexity 研究失敗：%s", e)
        return None

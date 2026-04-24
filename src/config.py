"""Configuration loader for auto-post-agent."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(verbose: bool = False) -> None:
    """設定專案 logging，verbose=True 時使用 DEBUG。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    # 降低第三方庫噪音
    for name in ("httpx", "httpcore", "openai", "PIL", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / "fonts"
DEMO_POST_DIR = PROJECT_ROOT / "demo post"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output")))
BACKGROUND_1 = DEMO_POST_DIR / "background 1.png"
BACKGROUND_2 = DEMO_POST_DIR / "background 2.png"

# API keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
REURL_API_KEY = os.getenv("REURL_API_KEY", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")

# LINE URL to shorten
LINE_URL = "https://line.me/ti/p/~home-tutor-tw"

# OpenRouter model
OPENROUTER_MODEL = "anthropic/claude-sonnet-4.6"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Perplexity Sonar Pro（透過 OpenRouter 呼叫，用於深度研究）
PERPLEXITY_MODEL = "perplexity/sonar-pro"

# 💡 sonar-deep-research：Perplexity 的 agentic 研究模型，內部會自動多輪搜尋＋推理
# ⚠️ 單次呼叫需 3-5 分鐘、成本比 sonar-pro 高 5-10 倍，適合「一次做透」的旗艦內容
PERPLEXITY_DEEP_MODEL = "perplexity/sonar-deep-research"

# 深度研究開關：true=用 sonar-deep-research，false=用 sonar-pro（單輪淺層）
RESEARCH_USE_DEEP = os.getenv("RESEARCH_USE_DEEP", "true").lower() == "true"

# 研究 HTTP timeout（秒）。sonar-deep-research 預設 6 分鐘，給 agentic 多輪搜尋足夠時間
RESEARCH_TIMEOUT = float(os.getenv("RESEARCH_TIMEOUT", "360"))

# 研究輸出 max_tokens。深度研究報告需要更大空間容納事實 + 觀點 + 方法三大段
RESEARCH_MAX_TOKENS = int(os.getenv("RESEARCH_MAX_TOKENS", "8000"))

# Google API key（預留給未來 Gemini Deep Research 等功能）
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Google Sheets 紀錄（可選，未設定時靜默略過） ──
GOOGLE_SHEETS_SA_JSON_PATH = os.getenv("GOOGLE_SHEETS_SA_JSON_PATH", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_SHEETS_TAB_NAME = os.getenv("GOOGLE_SHEETS_TAB_NAME", "Sheet1")

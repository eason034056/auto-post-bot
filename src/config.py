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

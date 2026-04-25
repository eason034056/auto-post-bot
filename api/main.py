"""
FastAPI backend for Threads 貼文自動生成 AI Agent.

Run: uvicorn api.main:app --reload --port 8000
"""
import io
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Ensure project root is in path when running as uvicorn api.main:app
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import json

from src.config import setup_logging
from src.config import OUTPUT_DIR
from src.html_image_generator import generate_images
from src.pipeline import run_pipeline, run_pipeline_streaming
from src.short_url import get_pinned_comment_text, shorten_url
from src.content_generator import OPENING_STYLES
from src.topic_generator import generate_topic, generate_topic_candidates

# Import MOCK_CONTENT from main for mock mode
from main import MOCK_CONTENT

setup_logging(verbose=False)

app = FastAPI(
    title="Threads 貼文自動生成 API",
    description="青椒家教 Threads 貼文生成服務",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---

class GenerateTopicResponse(BaseModel):
    topic: str


class TopicCandidate(BaseModel):
    angle: str
    topic: str


class GenerateTopicCandidatesResponse(BaseModel):
    candidates: list[TopicCandidate]
    recommended: str
    has_signals: bool


class GenerateRequest(BaseModel):
    topic: str
    style: str | None = None
    mock: bool = False
    research: bool = True


class GenerateResponse(BaseModel):
    hook: str
    structure_name: str
    content_strategy: list[str]
    discussion_question: str
    pinned_comment_text: str
    short_url: str
    output_dir: str
    image_count: int


class ImagesResponse(BaseModel):
    subdir: str
    images: list[str]


class LogSheetsRequest(BaseModel):
    subdir: str


class LogSheetsResponse(BaseModel):
    success: bool
    message: str
    already_logged: bool = False


# --- Routes ---

@app.get("/api/styles")
def api_get_styles():
    """取得可選的開場風格列表。"""
    return {"styles": OPENING_STYLES}


@app.get("/api/health")
def health():
    """Health check (for Docker / load balancers)."""
    return {"status": "ok", "message": "Threads 貼文自動生成 API"}


@app.post("/api/generate-topic", response_model=GenerateTopicResponse)
def api_generate_topic():
    """AI 產生貼文題目（單一推薦版本，向下相容）。"""
    try:
        topic = generate_topic()
        return GenerateTopicResponse(topic=topic)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate-topic-candidates", response_model=GenerateTopicCandidatesResponse)
def api_generate_topic_candidates():
    """AI 產生 10 個候選題目並標出推薦選項，供前端讓使用者挑選。"""
    try:
        result = generate_topic_candidates()
        return GenerateTopicCandidatesResponse(
            candidates=[TopicCandidate(**c) for c in result["candidates"]],
            recommended=result["recommended"],
            has_signals=result["has_signals"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001 — 任何後端異常都應該回 500 而非 500 全爛
        raise HTTPException(status_code=500, detail=f"題目生成失敗：{e}")


@app.post("/api/generate", response_model=GenerateResponse)
def api_generate(req: GenerateRequest):
    """執行完整 pipeline：內容生成 → 圖片製作 → 短網址。"""
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="題目不可為空")

    try:
        if req.mock:
            from src.pipeline import _save_metadata

            subdir = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_paths = generate_images(MOCK_CONTENT, output_subdir=subdir)
            short_url_str = shorten_url()
            pinned_text = get_pinned_comment_text(short_url_str)
            hook = MOCK_CONTENT.get("hook", "")
            structure_name = MOCK_CONTENT.get("structure_name", "")
            content_strategy = MOCK_CONTENT.get("content_strategy", [])
            discussion_question = MOCK_CONTENT.get("discussion_question", "")
            # mock 也存 metadata，讓使用者能測 log 按鈕
            _save_metadata(
                OUTPUT_DIR / subdir,
                {
                    "content": MOCK_CONTENT,
                    "hook": hook,
                    "structure_name": structure_name,
                    "content_strategy": content_strategy,
                    "discussion_question": discussion_question,
                    "short_url": short_url_str,
                    "pinned_comment_text": pinned_text,
                    "output_dir": OUTPUT_DIR / subdir,
                    "research_report": None,
                },
                topic=topic,
                style_hint=req.style,
            )
        else:
            result = run_pipeline(
                topic=topic,
                output_subdir=None,
                style_hint=req.style,
                research=req.research,
            )
            subdir = result["output_dir"].name
            hook = result.get("hook", "")
            structure_name = result.get("structure_name", "")
            content_strategy = result.get("content_strategy", [])
            discussion_question = result.get("discussion_question", "")
            pinned_text = result["pinned_comment_text"]
            short_url_str = result["short_url"]
            image_paths = result["image_paths"]

        # Save post_text.txt (same as CLI)
        txt_path = OUTPUT_DIR / subdir / "post_text.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("🏗️ 貼文結構：\n")
            f.write(f"{structure_name}\n")
            if content_strategy:
                f.write("策略節奏：" + " → ".join(content_strategy) + "\n")
            if discussion_question:
                f.write(f"引導討論：{discussion_question}\n\n")
            f.write("📝 貼文開頭（鉤子）：\n")
            f.write(f"{hook}\n\n")
            f.write("📌 置頂留言內容：\n")
            f.write(f"{pinned_text}\n")

        return GenerateResponse(
            hook=hook,
            structure_name=structure_name,
            content_strategy=content_strategy,
            discussion_question=discussion_question,
            pinned_comment_text=pinned_text,
            short_url=short_url_str,
            output_dir=subdir,
            image_count=len(image_paths),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _write_post_text(subdir: str, hook: str, structure_name: str,
                     content_strategy: list[str], discussion_question: str,
                     pinned_text: str) -> None:
    """寫 post_text.txt（與 CLI 一致），給使用者下載貼文文字用。"""
    txt_path = OUTPUT_DIR / subdir / "post_text.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("🏗️ 貼文結構：\n")
        f.write(f"{structure_name}\n")
        if content_strategy:
            f.write("策略節奏：" + " → ".join(content_strategy) + "\n")
        if discussion_question:
            f.write(f"引導討論：{discussion_question}\n\n")
        f.write("📝 貼文開頭（鉤子）：\n")
        f.write(f"{hook}\n\n")
        f.write("📌 置頂留言內容：\n")
        f.write(f"{pinned_text}\n")


@app.post("/api/generate-stream")
def api_generate_stream(req: GenerateRequest):
    """串流生成：SSE 端點，逐階段推送進度事件。

    事件格式（每個事件以 `data: <json>\\n\\n` 結尾）：
    - {"type":"progress","phase":"...","step":N,"total":M,"message":"...","sub_current":N?,"sub_total":M?}
    - {"type":"complete","result":{...與 GenerateResponse 同形}}
    - {"type":"error","detail":"..."}

    💡 用 fetch + ReadableStream 在前端解析（EventSource 不支援 POST，所以走 fetch）。
    """
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="題目不可為空")

    def event_stream():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # ── Mock 模式：直接回 complete，不需要進度 ───────────
        if req.mock:
            try:
                from src.pipeline import _save_metadata

                subdir = datetime.now().strftime("%Y%m%d_%H%M%S")
                yield sse({
                    "type": "progress", "phase": "mock", "step": 1, "total": 1,
                    "message": "Mock 模式：使用範例內容...",
                })
                image_paths = generate_images(MOCK_CONTENT, output_subdir=subdir)
                short_url_str = shorten_url()
                pinned_text = get_pinned_comment_text(short_url_str)
                hook = MOCK_CONTENT.get("hook", "")
                structure_name = MOCK_CONTENT.get("structure_name", "")
                content_strategy = MOCK_CONTENT.get("content_strategy", [])
                discussion_question = MOCK_CONTENT.get("discussion_question", "")

                _save_metadata(
                    OUTPUT_DIR / subdir,
                    {
                        "content": MOCK_CONTENT, "hook": hook,
                        "structure_name": structure_name,
                        "content_strategy": content_strategy,
                        "discussion_question": discussion_question,
                        "short_url": short_url_str,
                        "pinned_comment_text": pinned_text,
                        "output_dir": OUTPUT_DIR / subdir,
                        "research_report": None,
                    },
                    topic=topic, style_hint=req.style,
                )
                _write_post_text(subdir, hook, structure_name, content_strategy,
                                 discussion_question, pinned_text)

                yield sse({
                    "type": "complete",
                    "result": {
                        "hook": hook, "structure_name": structure_name,
                        "content_strategy": content_strategy,
                        "discussion_question": discussion_question,
                        "pinned_comment_text": pinned_text,
                        "short_url": short_url_str,
                        "output_dir": subdir,
                        "image_count": len(image_paths),
                    },
                })
            except Exception as e:  # noqa: BLE001
                yield sse({"type": "error", "detail": str(e)})
            return

        # ── 真實 pipeline：消費 streaming generator ─────────
        for event in run_pipeline_streaming(
            topic=topic,
            output_subdir=None,
            style_hint=req.style,
            research=req.research,
        ):
            if event.get("type") == "complete":
                # 把內部 result 重塑成 frontend 需要的 shape
                result = event["result"]
                subdir = result["output_dir"].name
                hook = result.get("hook", "")
                structure_name = result.get("structure_name", "")
                content_strategy = result.get("content_strategy", [])
                discussion_question = result.get("discussion_question", "")
                pinned_text = result["pinned_comment_text"]

                _write_post_text(subdir, hook, structure_name, content_strategy,
                                 discussion_question, pinned_text)

                yield sse({
                    "type": "complete",
                    "result": {
                        "hook": hook,
                        "structure_name": structure_name,
                        "content_strategy": content_strategy,
                        "discussion_question": discussion_question,
                        "pinned_comment_text": pinned_text,
                        "short_url": result["short_url"],
                        "output_dir": subdir,
                        "image_count": len(result["image_paths"]),
                    },
                })
            else:
                # progress / error 事件直接轉發
                yield sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 防止 nginx 等反代緩衝阻塞 SSE
            "Connection": "keep-alive",
        },
    )


@app.get("/api/output/{subdir}/images", response_model=ImagesResponse)
def api_get_images(subdir: str):
    """取得指定輸出資料夾的圖片檔名列表。"""
    out_dir = OUTPUT_DIR / subdir
    if not out_dir.exists() or not out_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到輸出資料夾: {subdir}")

    images = sorted(
        f.name for f in out_dir.iterdir()
        if f.suffix.lower() == ".png"
    )
    return ImagesResponse(subdir=subdir, images=images)


@app.post("/api/log-to-sheets", response_model=LogSheetsResponse)
def api_log_to_sheets(req: LogSheetsRequest):
    """使用者手動觸發：把指定 subdir 的貼文 metadata 寫入 Google Sheets。"""
    from src.sheets_logger import log_from_metadata
    result = log_from_metadata(req.subdir)
    return LogSheetsResponse(**result)


@app.get("/api/output/{subdir}/download-zip")
def api_download_zip(subdir: str):
    """下載指定輸出資料夾內所有圖片為 ZIP 檔。"""
    out_dir = OUTPUT_DIR / subdir
    if not out_dir.exists() or not out_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"找不到輸出資料夾: {subdir}")

    png_files = sorted(out_dir.glob("*.png"))
    if not png_files:
        raise HTTPException(status_code=404, detail="該資料夾內沒有圖片")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in png_files:
            zf.write(f, f.name)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={subdir}.zip"},
    )


# Mount static files for output images (with download-friendly headers)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# Serve frontend (when running in Docker)
_frontend_dist = os.getenv("FRONTEND_DIST_PATH")
if _frontend_dist and Path(_frontend_dist).exists():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")

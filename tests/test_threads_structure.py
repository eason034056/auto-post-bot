import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import GenerateRequest, api_generate
from src.content_generator import _clean_model_response, _validate_content_payload
from src.pipeline import run_pipeline


def _build_valid_content():
    return {
        "hook": "以前我也想不通，孩子明明坐在書桌前，為什麼成績還是沒有起色？",
        "structure_name": "Threads 爆文六段結構",
        "content_strategy": [
            "好奇開頭",
            "強烈難題",
            "結果預告",
            "對話還原",
            "規律總結",
            "引導思考",
        ],
        "discussion_question": "你家孩子最常出現哪一種看起來有讀、其實沒吸收的狀況？",
        "slides": [
            {"type": "title", "content": "孩子明明有坐下來讀\n為什麼還是沒有進步？"},
            {
                "type": "bullet_list",
                "title": "很多家長都卡在這裡",
                "items": ["孩子每天都有碰書", "成績卻一直沒有起色"],
                "footer": "真正的問題，常常不是讀太少。",
            },
            {
                "type": "summary",
                "content": "先別急著加時間，先看有沒有真的吸收。",
            },
            {
                "type": "case_study",
                "title": "那天我和孩子的對話",
                "problem": "我問他今天讀了什麼，他只說讀很多。",
                "solution": "我改問：你可不可以用自己的話講一次？",
                "result": "他才發現自己其實只是看過，沒有真的理解。",
            },
            {"type": "summary", "content": "很多努力沒效果，不是因為不認真，而是沒有被轉成理解。"},
            {
                "type": "cta",
                "content": "青椒老師專業家教服務\n服務地區: 新竹 | 台北\n專業領域: 國高中小家教媒合\n點擊留言連結直接加入官方Line好友",
            },
        ],
    }


class ContentValidationTests(unittest.TestCase):
    def test_clean_model_response_strips_markdown_code_fence(self):
        raw = """```json\n{"hook":"測試","slides":[]}\n```"""

        cleaned = _clean_model_response(raw)

        self.assertEqual(cleaned, '{"hook":"測試","slides":[]}')

    def test_validate_content_payload_accepts_threads_viral_structure(self):
        payload = _build_valid_content()

        validated = _validate_content_payload(payload)

        self.assertEqual(validated["structure_name"], "Threads 爆文六段結構")
        self.assertEqual(validated["discussion_question"], payload["discussion_question"])
        self.assertEqual(validated["slides"][-1]["type"], "cta")

    def test_validate_content_payload_rejects_missing_discussion_question(self):
        payload = _build_valid_content()
        payload["discussion_question"] = "   "

        with self.assertRaises(ValueError):
            _validate_content_payload(payload)


class PipelineMetadataTests(unittest.TestCase):
    @patch("src.pipeline.shorten_url", return_value="https://short.url/test")
    @patch("src.pipeline.get_pinned_comment_text", return_value="免費一對一家教配對歡迎點擊連結或QR Code加入官方 LINE：https://short.url/test")
    @patch("src.pipeline.generate_images", return_value=[Path("output/demo/slide_01.png")])
    @patch("src.pipeline.generate_content")
    def test_run_pipeline_returns_structure_metadata(
        self,
        mock_generate_content,
        _mock_generate_images,
        _mock_get_pinned_comment_text,
        _mock_shorten_url,
    ):
        mock_generate_content.return_value = _build_valid_content()

        result = run_pipeline("假讀書", output_subdir="demo")

        self.assertEqual(result["structure_name"], "Threads 爆文六段結構")
        self.assertEqual(result["content_strategy"][0], "好奇開頭")
        self.assertTrue(result["discussion_question"].startswith("你家孩子"))


class ApiResponseTests(unittest.TestCase):
    @patch("api.main.run_pipeline")
    def test_api_generate_returns_structure_fields(self, mock_run_pipeline):
        payload = _build_valid_content()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "demo"
            output_dir.mkdir(parents=True, exist_ok=True)
            mock_run_pipeline.return_value = {
                "content": payload,
                "hook": payload["hook"],
                "structure_name": payload["structure_name"],
                "content_strategy": payload["content_strategy"],
                "discussion_question": payload["discussion_question"],
                "image_paths": [output_dir / "slide_01.png"],
                "short_url": "https://short.url/test",
                "pinned_comment_text": "免費一對一家教配對歡迎點擊連結或QR Code加入官方 LINE：https://short.url/test",
                "output_dir": output_dir,
            }

            with patch("api.main.OUTPUT_DIR", Path(tmpdir)):
                response = api_generate(GenerateRequest(topic="假讀書"))

        self.assertEqual(response.structure_name, "Threads 爆文六段結構")
        self.assertEqual(response.content_strategy[-1], "引導思考")
        self.assertIn("你家孩子", response.discussion_question)


if __name__ == "__main__":
    unittest.main()

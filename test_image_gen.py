"""Test image generation without API call."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.image_generator import generate_images

# Mock content matching the expected structure
MOCK_CONTENT = {
    "slides": [
        {"type": "title", "content": "孩子明明讀書，\n為什麼腦袋卻沒在吸收？"},
        {
            "type": "bullet_list",
            "title": "什麼是假讀書?",
            "items": [
                "眼睛看著課本，腦袋在放空",
                "筆記抄得很漂亮，但不知道在寫什麼",
                "讀完一頁，完全不記得剛才讀了什麼",
                "遇到不懂的地方，直接跳過",
            ],
            "footer": "看起來在讀書，但其實「沒有真正在思考」",
        },
        {
            "type": "numbered",
            "number": 1,
            "title": "用「自己的話」說一遍",
            "content": "讀完一個段落後，不要馬上往下讀\n而是問孩子：「你可以用自己的話解釋一遍嗎？」\n如果說不出來 → 代表沒真的懂\n如果能說出來 → 才是真的吸收了",
            "example": "讀完「光合作用」後\n不是背定義，而是說：「就是植物用陽光做食物」",
        },
        {
            "type": "summary",
            "content": "關鍵不是讀更久\n而是「讀得更有效」",
        },
        {
            "type": "cta",
            "content": "青椒老師專業家教服務\n服務地區: 新竹 | 台北\n專業領域: 國高中小家教媒合\n點擊留言連結直接加入官方Line好友",
        },
    ]
}

if __name__ == "__main__":
    paths = generate_images(MOCK_CONTENT, output_subdir="test_run")
    print(f"Generated {len(paths)} images:")
    for p in paths:
        print(f"  {p}")

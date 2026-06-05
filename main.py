#!/usr/bin/env python3
"""
Threads 貼文自動生成 AI Agent

Usage:
  python main.py "假讀書"                   # 預設啟用深度研究
  python main.py --auto-topic              # AI 自動產生題目
  python main.py "孩子拖延怎麼辦" --style "情境描述"
  python main.py "假讀書" --no-research    # 停用深度研究（純 AI 產生）
  python main.py "假讀書" --mock           # 使用範例內容測試（不需 API key）
  python main.py "假讀書" -v                # 詳細輸出（DEBUG）
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import setup_logging
from src.pipeline import run_pipeline
from src.topic_generator import generate_topic

logger = logging.getLogger(__name__)


MOCK_CONTENT = {
    "hook": "孩子明明有在讀書，為什麼腦袋卻沒在吸收？很多家長都有這個疑問。",
    "structure_name": "Threads 爆文六段結構",
    "content_strategy": [
        "好奇開頭",
        "強烈難題",
        "結果預告",
        "對話還原",
        "規律總結",
        "引導思考",
    ],
    "discussion_question": "你家孩子也有明明讀很久，卻說不出到底學了什麼的時候嗎？",
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
            "content": "讀完一個段落後，不要馬上往下讀\n而是問孩子：「你可以用自己的話解釋一遍嗎？」",
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
    ],
    # Facebook 一文一圖的範例內容（mock 模式預覽 FB 分區用）
    "facebook": {
        "article": (
            "你家孩子讀了兩個小時書，結果月考還是考爛——這不是孩子不努力，是那兩小時根本沒進去。\n\n"
            "我之前帶過一個國二的女生，她媽媽說「她每天讀到十一點，我不知道還能怎樣」。我去問她，"
            "她說都在抄課文、抄單字。兩小時，抄完，收書，睡覺。下次月考英文 52 分。\n\n"
            "問題不是時間，是她讀的時候腦子幾乎關機。抄寫的時候手在動、眼睛在看，但沒有思考，"
            "隔天起床幾乎全忘。這就是假讀書——看起來在讀，大腦沒收到訊號。\n\n"
            "破解方法很簡單：讀完一段，把課本蓋起來，用自己的話講一遍剛剛讀了什麼。說得出來代表有進去，"
            "說不出來代表剛才在放空。那女生用這方法之後說「讀書變好累」——對，因為她終於真的在讀了。"
            "後來英文爬到 74 分，花的時間反而更少。\n\n"
            "你家孩子讀書的時候，是用抄的、用背的，還是真的有在消化？"
        ),
        "cover": {
            "tag": "方法 / METHOD",
            "title": "讀了兩小時卻什麼都沒進去",
            "subtitle": "假讀書比不讀更難被發現",
        },
        "discussion_question": "你家孩子讀書都用什麼方式？有沒有發現他其實是在「假讀」的跡象？",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Threads 貼文自動生成")
    parser.add_argument("topic", nargs="?", help="貼文題目（例如：假讀書）")
    parser.add_argument("--auto-topic", action="store_true", help="由 AI 自動產生題目")
    parser.add_argument("--style", help="開場風格（可選）", default=None)
    parser.add_argument("--no-research", action="store_true", help="停用 Perplexity 深度研究（預設啟用）")
    parser.add_argument("--output", "-o", help="輸出資料夾名稱", default=None)
    parser.add_argument("--mock", action="store_true", help="使用範例內容測試（不需 API key）")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細輸出（DEBUG）")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # 題目來源：手動指定 或 AI 產生
    if args.auto_topic:
        if args.topic:
            parser.error("--auto-topic 與手動題目不可同時使用")
        logger.info("AI 產生題目中...")
        topic = generate_topic()
        logger.info("題目：%s", topic)
    elif args.topic:
        topic = args.topic
        logger.info("使用手動題目：%s", topic)
    else:
        parser.error("請提供題目，或使用 --auto-topic 由 AI 產生")

    if args.mock:
        from src.config import OUTPUT_DIR
        from src.html_image_generator import generate_images
        from src.short_url import get_pinned_comment_text, shorten_url

        logger.info("使用 mock 模式（不呼叫 API）")
        subdir = args.output or datetime.now().strftime("%Y%m%d_%H%M%S")
        image_paths = generate_images(MOCK_CONTENT, output_subdir=subdir)
        short_url = shorten_url()
        pinned_text = get_pinned_comment_text(short_url)
        result = {
            "content": MOCK_CONTENT,
            "hook": MOCK_CONTENT.get("hook", ""),
            "image_paths": image_paths,
            "short_url": short_url,
            "pinned_comment_text": pinned_text,
            "output_dir": OUTPUT_DIR / subdir,
        }
    else:
        result = run_pipeline(
            topic=topic,
            output_subdir=args.output,
            style_hint=args.style,
            research=not args.no_research,
        )

    logger.info("完成！輸出目錄：%s", result["output_dir"])
    logger.info("圖片：%d 張", len(result["image_paths"]))
    hook = result.get("hook", "")
    pinned = result["pinned_comment_text"]

    # 存成 .txt 檔（與 terminal 顯示相同內容）
    txt_path = Path(result["output_dir"]) / "post_text.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("🏗️ 貼文結構：\n")
        f.write(f"{result['content'].get('structure_name', '')}\n")
        strategy = result["content"].get("content_strategy", [])
        if strategy:
            f.write("策略節奏：" + " → ".join(strategy) + "\n")
        discussion_question = result["content"].get("discussion_question", "")
        if discussion_question:
            f.write(f"引導討論：{discussion_question}\n\n")
        f.write("📝 貼文開頭（鉤子）：\n")
        f.write(f"{hook}\n\n")
        f.write("📌 置頂留言內容：\n")
        f.write(f"{pinned}\n")
    logger.info("貼文文字已存：%s", txt_path)

    # 若有研究報告，另存為獨立檔案
    research_report = result.get("research_report")
    if research_report:
        research_path = Path(result["output_dir"]) / "research_report.txt"
        with open(research_path, "w", encoding="utf-8") as f:
            f.write(f"深度研究報告：{topic}\n")
            f.write("=" * 50 + "\n\n")
            f.write(research_report)
        logger.info("研究報告已存：%s", research_path)

    print(f"\n✅ 完成！輸出目錄：{result['output_dir']}")
    print(f"   圖片：{len(result['image_paths'])} 張")
    if hook:
        print(f"\n📝 貼文開頭（鉤子）：\n{hook}\n")
    print(f"📌 置頂留言內容：\n{pinned}\n")


if __name__ == "__main__":
    main()

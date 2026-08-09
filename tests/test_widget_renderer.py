from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from widget_renderer import CATEGORIES, render_all, select_top_news


class WidgetRendererTests(unittest.TestCase):
    def _feed(self) -> dict[str, object]:
        briefings = []
        for category in ("경제", "산업", "증권", "국제"):
            for rank in range(1, 6):
                briefings.append(
                    {
                        "id": f"{category}-{rank}",
                        "type": "past",
                        "category": category,
                        "title": f"{category} <주요 뉴스> {rank}",
                        "summary": f"{category} 뉴스 {rank} 요약",
                        "importance_score": 100 - rank,
                        "published_at": f"2026-08-09T1{rank}:00:00+09:00",
                        "source_name": "테스트 매체",
                        "source_url": "https://example.com/news",
                        "source_count": rank,
                    }
                )
        return {
            "generated_at": "2026-08-09T16:37:00+09:00",
            "briefings": briefings,
        }

    def test_each_category_gets_a_170_pixel_widget_and_top4_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "briefing.json"
            output_dir = root / "widgets"
            feed_path.write_text(
                json.dumps(self._feed(), ensure_ascii=False), encoding="utf-8"
            )

            render_all(feed_path, output_dir)

            for category in CATEGORIES:
                with Image.open(output_dir / f"{category.slug}.png") as image:
                    self.assertEqual(image.size, (170, 170))
                    self.assertEqual(image.format, "PNG")
                html = (output_dir / f"{category.slug}.html").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"ABO {category.name} 실시간 인기 뉴스 TOP4", html)
                self.assertEqual(html.count('class="news-card"'), 4)
                self.assertIn("&lt;주요 뉴스&gt;", html)

    def test_ranking_uses_importance_and_keeps_only_four(self) -> None:
        selected = select_top_news(self._feed(), "경제")

        self.assertEqual(len(selected), 4)
        self.assertEqual(selected[0]["title"], "경제 <주요 뉴스> 1")
        self.assertEqual(selected[-1]["title"], "경제 <주요 뉴스> 4")


if __name__ == "__main__":
    unittest.main()

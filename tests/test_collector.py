from __future__ import annotations

import unittest
from collections import Counter
from datetime import datetime

from collector import CATEGORIES, SEOUL, build_feed


class CollectorTests(unittest.TestCase):
    def test_every_category_has_four_past_and_upcoming_items(self) -> None:
        feed = build_feed(datetime(2026, 8, 4, 12, tzinfo=SEOUL))
        items = feed["briefings"]
        for category in CATEGORIES[1:]:
            counts = Counter(
                item["type"] for item in items if item["category"] == category
            )
            self.assertEqual(counts["past"], 4)
            self.assertEqual(counts["upcoming"], 4)

    def test_required_sections_and_example_disclosure(self) -> None:
        feed = build_feed(datetime(2026, 8, 4, 12, tzinfo=SEOUL))
        types = Counter(item["type"] for item in feed["briefings"])
        self.assertEqual(types["stock_issue"], 4)
        self.assertEqual(types["stock_calendar"], 4)
        self.assertTrue(feed["markets"])
        self.assertTrue(all(item["is_example"] for item in feed["briefings"]))


if __name__ == "__main__":
    unittest.main()

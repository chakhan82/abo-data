from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from collector import (
    CATEGORIES,
    SEOUL,
    _find_event_time,
    parse_bok_schedules,
    parse_google_news,
    parse_kostat_schedules,
    parse_yahoo_market,
    validate_feed,
)


class ParserTests(unittest.TestCase):
    def test_google_news_keeps_real_source_and_publication_time(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel><item>
          <title>한국 경제지표 발표 - 테스트뉴스</title>
          <link>https://news.google.com/rss/articles/real</link>
          <pubDate>Tue, 04 Aug 2026 09:00:00 GMT</pubDate>
          <source url="https://news.example.org">테스트뉴스</source>
        </item></channel></rss>"""
        stories = parse_google_news(xml)
        self.assertEqual(stories[0].title, "한국 경제지표 발표")
        self.assertEqual(stories[0].source, "테스트뉴스")
        self.assertEqual(stories[0].published_at.hour, 18)

    def test_future_date_without_time_is_not_given_a_false_confirmed_time(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        event = _find_event_time("예비 부모 특별교육 8월 7일 개최", now, now)
        self.assertIsNotNone(event)
        moment, time_confirmed = event or (now, True)
        self.assertEqual((moment.month, moment.day), (8, 7))
        self.assertFalse(time_confirmed)

    def test_bare_future_day_in_schedule_headline_is_detected(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        event = _find_event_time("전국 과학축전 7일 개최 예정", now, now)
        self.assertIsNotNone(event)
        moment, time_confirmed = event or (now, True)
        self.assertEqual((moment.month, moment.day, moment.hour), (8, 7, 12))
        self.assertFalse(time_confirmed)

    def test_past_bare_day_is_not_moved_to_next_month(self) -> None:
        now = datetime(2026, 8, 4, 22, tzinfo=SEOUL)
        self.assertIsNone(_find_event_time("정책회의 3일 개최", now, now))

    def test_bare_day_is_inferred_from_article_month_not_current_month(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        published = datetime(2026, 7, 1, 9, tzinfo=SEOUL)
        self.assertIsNone(
            _find_event_time(
                "정책 발표 5일",
                published,
                now,
                allow_bare_day=True,
            )
        )

    def test_duration_count_is_not_mistaken_for_calendar_day(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        self.assertIsNone(
            _find_event_time(
                "국내 증시 5일 연속 상승",
                now,
                now,
                allow_bare_day=True,
            )
        )

    def test_rescheduled_headline_uses_new_date(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        event = _find_event_time(
            "경기 일정 8월 8일→8월 10일로 변경",
            now,
            now,
            allow_bare_day=True,
        )
        self.assertIsNotNone(event)
        moment, _ = event or (now, False)
        self.assertEqual((moment.month, moment.day), (8, 10))

    def test_cancelled_schedule_is_excluded(self) -> None:
        now = datetime(2026, 8, 4, 10, tzinfo=SEOUL)
        self.assertIsNone(
            _find_event_time(
                "프로야구 8월 5일 경기 폭염으로 취소",
                now,
                now,
                allow_bare_day=True,
            )
        )

    def test_official_schedule_tables_keep_announced_clock_time(self) -> None:
        kostat = """<table><tr><td>08.05.( 수 )</td><td>12:00</td>
        <td>고령층 부가조사 결과</td><td>고용통계과</td></tr></table>"""
        bok = """<table><tr><td>2026-08-06</td><td>8:00</td>
        <td class="title">2026년 6월 국제수지(잠정)</td></tr></table>"""
        self.assertEqual(parse_kostat_schedules(kostat, 2026)[0][0].hour, 12)
        self.assertEqual(parse_bok_schedules(bok)[0][0].hour, 8)

    def test_market_change_is_calculated_from_previous_close(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": 110,
                            "previousClose": 100,
                            "regularMarketTime": 1785852000,
                            "marketState": "CLOSED",
                        },
                        "timestamp": [1785852000],
                    }
                ]
            }
        }
        market = parse_yahoo_market(
            payload,
            symbol="TEST",
            display_name="테스트",
            currency="pt",
            multiplier=1,
        )
        self.assertEqual(market["change"], 10)
        self.assertEqual(market["change_percent"], 10)
        self.assertFalse(market["is_example"])


class PublishedFeedTests(unittest.TestCase):
    def test_checked_in_feed_contains_only_real_sources(self) -> None:
        path = Path(__file__).parents[1] / "public" / "data" / "briefing.json"
        feed = json.loads(path.read_text(encoding="utf-8"))
        validate_feed(feed)
        self.assertFalse(feed["is_example"])
        self.assertTrue(all(not item["is_example"] for item in feed["briefings"]))
        self.assertGreaterEqual(len(feed["markets"]), 6)
        generated_at = datetime.fromisoformat(feed["generated_at"])
        yesterday = (generated_at - timedelta(days=1)).date()
        stock_issues = [
            item for item in feed["briefings"] if item["type"] == "stock_issue"
        ]
        self.assertGreaterEqual(len(stock_issues), 4)
        self.assertTrue(
            all(
                datetime.fromisoformat(item["published_at"]).date() == yesterday
                for item in stock_issues
            )
        )
        for category in CATEGORIES[1:]:
            count = sum(
                item["type"] == "past" and item["category"] == category
                for item in feed["briefings"]
            )
            self.assertGreaterEqual(count, 4, category)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")
CATEGORIES = [
    "전체",
    "사회",
    "경제",
    "산업",
    "증권",
    "부동산",
    "과학·기술",
    "교육",
    "국제",
    "정치",
    "문화",
    "스포츠",
]

NEWS_QUERIES = {
    "사회": "한국 (사회 OR 안전 OR 복지 OR 사건 OR 사고)",
    "경제": "한국 (경제 OR 물가 OR 고용 OR 수출 OR 소비)",
    "산업": "한국 (산업 OR 기업 OR 반도체 OR 자동차 OR 배터리 OR 조선)",
    "증권": "국내 (증시 OR 주식 OR 코스피 OR 코스닥 OR 공시)",
    "부동산": "한국 (부동산 OR 주택 OR 아파트 OR 전세 OR 분양)",
    "과학·기술": "(과학 OR 기술 OR 인공지능 OR AI OR 우주 OR 연구 OR 보안)",
    "교육": "한국 (교육 OR 학교 OR 대학 OR 입시 OR 교사 OR 학생)",
    "국제": "(국제 OR 세계 OR 외교 OR 미국 OR 중국 OR 일본 OR 유럽)",
    "정치": "한국 (정치 OR 국회 OR 정부 OR 대통령 OR 정당)",
    "문화": "한국 (문화 OR 예술 OR 영화 OR 공연 OR 방송 OR 출판)",
    "스포츠": "한국 (스포츠 OR 야구 OR 축구 OR 배구 OR 농구 OR 경기)",
}

SCHEDULE_QUERIES = {
    "사회": "한국 (사회 OR 안전 OR 복지 OR 행사) (예정 OR 개최 OR 시행 OR 발표 OR 회의 OR 설명회)",
    "경제": "한국 (경제 OR 물가 OR 고용 OR 수출 OR 금리) (발표 OR 공표 OR 회의 OR 일정)",
    "산업": "한국 (산업 OR 기업 OR 반도체 OR 자동차 OR 배터리) (발표 OR 출시 OR 개최 OR 예정 OR 일정)",
    "증권": "국내 (증시 OR 주식 OR 상장 OR 공모주 OR 실적) (예정 OR 발표 OR 거래 OR 공시 OR 일정)",
    "부동산": "한국 (부동산 OR 청약 OR 분양 OR 공급 OR 주택) (예정 OR 발표 OR 접수 OR 시행 OR 일정)",
    "과학·기술": "한국 (과학 OR 기술 OR AI OR 우주 OR 연구) (발표 OR 공개 OR 발사 OR 개최 OR 일정)",
    "교육": "한국 (교육 OR 학교 OR 대학 OR 입시 OR 수능) (발표 OR 접수 OR 시행 OR 설명회 OR 일정)",
    "국제": "(국제 OR 미국 OR 중국 OR 일본 OR 유럽) (정상회담 OR 회의 OR 선거 OR 발표 OR 일정)",
    "정치": "한국 (국회 OR 정부 OR 대통령 OR 선거 OR 법안) (회의 OR 표결 OR 발표 OR 예정 OR 일정)",
    "문화": "한국 (문화 OR 공연 OR 전시 OR 영화 OR 축제) (개막 OR 개봉 OR 개최 OR 공개 OR 일정)",
    "스포츠": "한국 (스포츠 OR 야구 OR 축구 OR 농구 OR 배구 OR 골프) (경기 OR 개막 OR 개최 OR 일정)",
}

CATEGORY_KEYWORDS = {
    "사회": (
        "사회",
        "안전",
        "경찰",
        "법원",
        "검찰",
        "사고",
        "재난",
        "복지",
        "의료",
        "날씨",
        "폭염",
        "호우",
    ),
    "경제": (
        "경제",
        "물가",
        "금리",
        "고용",
        "수출",
        "수입",
        "소비",
        "무역",
        "환율",
        "한국은행",
        "국가데이터처",
    ),
    "산업": (
        "산업",
        "기업",
        "반도체",
        "자동차",
        "배터리",
        "조선",
        "항공",
        "에너지",
        "공급망",
        "공장",
    ),
    "증권": (
        "증시",
        "주식",
        "코스피",
        "코스닥",
        "상장",
        "공시",
        "실적",
        "주가",
        "투자",
        "증권",
    ),
    "부동산": ("부동산", "주택", "아파트", "전세", "월세", "분양", "재건축", "토지"),
    "과학·기술": (
        "과학",
        "기술",
        "인공지능",
        "AI",
        "우주",
        "연구",
        "로봇",
        "보안",
        "플랫폼",
        "데이터센터",
    ),
    "교육": ("교육", "학교", "대학", "입시", "교사", "학생", "수능", "학원"),
    "국제": (
        "국제",
        "미국",
        "중국",
        "일본",
        "유럽",
        "러시아",
        "우크라이나",
        "중동",
        "외교",
        "정상회담",
    ),
    "정치": ("정치", "국회", "정부", "대통령", "장관", "여당", "야당", "선거", "법안"),
    "문화": (
        "문화",
        "예술",
        "영화",
        "공연",
        "방송",
        "드라마",
        "음악",
        "출판",
        "전시",
        "축제",
    ),
    "스포츠": (
        "스포츠",
        "야구",
        "축구",
        "농구",
        "배구",
        "골프",
        "KBO",
        "K리그",
        "경기",
        "선수",
        "감독",
    ),
}

IMPACT_TEXT = {
    "사회": "생활 안전과 공공서비스에 미칠 영향을 살펴볼 사안입니다.",
    "경제": "물가·고용·소비 심리와 정책 판단에 영향을 줄 수 있습니다.",
    "산업": "기업 투자와 공급망, 관련 업종의 경쟁 구도에 영향을 줄 수 있습니다.",
    "증권": "시장 수급과 투자 심리에 영향을 줄 수 있는 재료입니다.",
    "부동산": "주거 비용과 거래 심리, 공급 계획에 영향을 줄 수 있습니다.",
    "과학·기술": "기술 경쟁과 산업 적용 속도에 영향을 줄 수 있습니다.",
    "교육": "학생·학부모와 교육 현장의 준비에 영향을 줄 수 있습니다.",
    "국제": "외교·안보와 국내 경제 환경에 파급될 수 있습니다.",
    "정치": "정책 추진과 국회 논의의 방향에 영향을 줄 수 있습니다.",
    "문화": "콘텐츠 소비와 문화 산업의 흐름에 영향을 줄 수 있습니다.",
    "스포츠": "경기 운영과 순위 경쟁, 팬들의 관전 흐름에 영향을 줄 수 있습니다.",
}

COMMENT_TEXT = {
    "사회": "당국의 후속 조치와 현장 안전 안내가 어떻게 이어지는지 확인해 보세요.",
    "경제": "한 번의 수치보다 이전 발표와의 변화, 체감경기의 방향을 함께 보는 게 좋습니다.",
    "산업": "발표 내용이 실제 투자·생산 일정으로 이어지는지가 다음 관전 포인트입니다.",
    "증권": "제목만으로 매매를 판단하지 말고 공시 원문과 거래소 수치를 함께 확인하세요.",
    "부동산": "지역과 주택 유형에 따라 영향이 다를 수 있어 세부 조건을 나눠 볼 필요가 있습니다.",
    "과학·기술": "기술 발표 자체보다 상용화 시점과 실제 적용 범위를 함께 살펴보면 좋겠습니다.",
    "교육": "적용 대상과 시행 시점이 누구에게 달라지는지 후속 안내를 확인해 보세요.",
    "국제": "현지 발표와 국내 파급효과 사이에는 시차가 있어 후속 보도를 함께 보는 게 좋습니다.",
    "정치": "발언보다 실제 의결·시행 일정이 어떻게 정해지는지가 중요합니다.",
    "문화": "공개 일정과 관람·시청 방법이 바뀔 수 있으니 공식 안내를 확인해 보세요.",
    "스포츠": "경기 시간과 출전 명단은 직전까지 바뀔 수 있어 공식 발표를 다시 확인해 주세요.",
}

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR%3Ako"
)
YONHAP_RSS_URL = "https://www.yna.co.kr/rss/news.xml"
DART_RSS_URL = "https://dart.fss.or.kr/api/todayRSS.xml"
KOSTAT_SCHEDULE_URL = (
    "https://www.kostat.go.kr/newsPln.es?mid=a10305000000&oa_mm={month:02d}"
)
BOK_SCHEDULE_URL = (
    "https://www.bok.or.kr/portal/stats/statsPublictSchdul/"
    "listCldr.do?date={year:04d}-{month:02d}&menuNo=200775"
)

MARKET_SYMBOLS = (
    ("USDKRW", "원·달러", "KRW=X", "KRW", 1.0),
    ("JPYKRW", "엔·원(100엔)", "JPYKRW=X", "KRW", 100.0),
    ("EURKRW", "유로·원", "EURKRW=X", "KRW", 1.0),
    ("KOSPI", "코스피", "^KS11", "pt", 1.0),
    ("KOSDAQ", "코스닥", "^KQ11", "pt", 1.0),
    ("DJI", "다우존스", "^DJI", "pt", 1.0),
    ("IXIC", "나스닥", "^IXIC", "pt", 1.0),
    ("SPX", "S&P 500", "^GSPC", "pt", 1.0),
    ("WTI", "국제유가(WTI)", "CL=F", "USD", 1.0),
    ("GOLD", "금", "GC=F", "USD", 1.0),
)


class CollectionError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, timeout: float = 18.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    def text(self, url: str) -> str:
        data = self.bytes(url)
        return data.decode("utf-8", errors="replace")

    def json(self, url: str) -> Any:
        return json.loads(self.text(url))

    def bytes(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "ABO/1.2 (+https://github.com/chakhan82/abo-data)",
                        "Accept": "application/json, application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
                    },
                )
                with urlopen(request, timeout=self.timeout) as response:
                    return response.read()
            except Exception as error:  # network errors vary across runners
                last_error = error
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
        raise CollectionError(f"{url}: {last_error}")


@dataclass(frozen=True)
class Story:
    title: str
    link: str
    source: str
    published_at: datetime
    summary: str = ""


def _text(element: ET.Element | None) -> str:
    return "" if element is None or element.text is None else element.text.strip()


def _clean_html(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _shorten(value: str, limit: int = 190) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,.;:") + "…"


def _parse_rss_date(value: str) -> datetime:
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(SEOUL)


def parse_google_news(xml_text: str) -> list[Story]:
    root = ET.fromstring(xml_text)
    stories: list[Story] = []
    for item in root.findall("./channel/item"):
        source_element = item.find("source")
        source = _text(source_element) or "언론사"
        title = _text(item.find("title"))
        suffix = f" - {source}"
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
        link = _text(item.find("link"))
        published = _text(item.find("pubDate"))
        if (
            not title
            or not link
            or not published
            or len(re.findall(r"[가-힣]", title)) < 2
        ):
            continue
        stories.append(
            Story(
                title=title,
                link=link,
                source=source,
                published_at=_parse_rss_date(published),
            )
        )
    return stories


def parse_yonhap_news(xml_text: str) -> list[Story]:
    root = ET.fromstring(xml_text)
    stories: list[Story] = []
    for item in root.findall("./channel/item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        published = _text(item.find("pubDate"))
        description = _clean_html(_text(item.find("description")))
        description = re.sub(r"^\([^)]*=연합뉴스\)\s*", "", description)
        description = re.sub(r"^[가-힣A-Za-z·\s]{2,40}\s+기자\s*=\s*", "", description)
        if len(description) < 20:
            description = ""
        if title and link and published:
            stories.append(
                Story(
                    title=title,
                    link=link,
                    source="연합뉴스",
                    published_at=_parse_rss_date(published),
                    summary=_shorten(description),
                )
            )
    return stories


def classify_category(title: str, default: str | None = None) -> str | None:
    scores = {
        category: sum(
            2 if keyword.lower() in title.lower() else 0 for keyword in keywords
        )
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else default


def _story_summary(story: Story) -> str:
    if story.summary:
        return story.summary
    return _shorten(
        f"{story.title} 관련 소식입니다. 공개된 제목과 게시 시각을 기준으로 정리했으며 세부 내용은 원문에서 확인할 수 있습니다."
    )


def _keywords(title: str, category: str) -> list[str]:
    words = re.findall(r"[가-힣A-Za-z0-9]+", title)
    ignored = {"관련", "대한", "기자", "뉴스", "오늘", "내일", "오는", "발표"}
    result = [category]
    for word in sorted(words, key=len, reverse=True):
        if len(word) < 2 or word in ignored or word in result:
            continue
        result.append(word)
        if len(result) == 4:
            break
    return result


def _stable_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()[:18]
    return f"{prefix}-{digest}"


def _importance(title: str, published_at: datetime, now: datetime) -> float:
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
    score = 96.0 - min(age_hours, 120) * 0.18
    if any(
        word in title
        for word in (
            "확정",
            "발표",
            "속보",
            "경보",
            "금리",
            "물가",
            "실적",
            "공시",
            "합의",
        )
    ):
        score += 2.5
    if any(word in title for word in ("포토", "운세", "화보")):
        score -= 8
    return round(max(55.0, min(99.0, score)), 1)


def _briefing_from_story(
    story: Story,
    *,
    category: str,
    item_type: str,
    now: datetime,
    scheduled_at: datetime | None = None,
    time_confirmed: bool = True,
    schedule_status: str | None = None,
) -> dict[str, object]:
    is_future = item_type in {"upcoming", "stock_calendar"}
    event_time = scheduled_at if is_future else story.published_at
    if event_time is None:
        raise ValueError("future briefing requires scheduled_at")
    return {
        "id": _stable_id(item_type, category, story.link, event_time.isoformat()),
        "type": item_type,
        "category": category,
        "title": story.title,
        "summary": _story_summary(story),
        "ai_comment": COMMENT_TEXT[category],
        "impact": IMPACT_TEXT[category],
        "importance_score": _importance(story.title, story.published_at, now),
        "published_at": None if is_future else event_time.isoformat(),
        "scheduled_at": event_time.isoformat() if is_future else None,
        "event_time_confirmed": time_confirmed,
        "source_name": story.source,
        "source_url": story.link,
        "related_keywords": _keywords(story.title, category),
        "related_companies": [],
        "schedule_status": schedule_status if is_future else None,
        "source_count": 1,
        "confidence": 0.92 if story.summary else 0.82,
        "is_example": False,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def _deduplicate(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in items:
        normalized_title = re.sub(r"[^0-9a-z가-힣]", "", str(item["title"]).lower())
        key = f"{item.get('type', '')}:{normalized_title}"
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _find_event_time(
    title: str,
    published_at: datetime,
    now: datetime,
    *,
    allow_bare_day: bool = False,
) -> tuple[datetime, bool] | None:
    date_value: datetime | None = None
    absolute_matches = list(
        re.finditer(r"(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일", title)
    )
    if "취소" in title and len(absolute_matches) <= 1:
        return None
    absolute = (
        absolute_matches[-1]
        if len(absolute_matches) > 1
        and any(keyword in title for keyword in ("변경", "연기", "→"))
        else (absolute_matches[0] if absolute_matches else None)
    )
    if absolute:
        year = int(absolute.group(1) or now.year)
        date_value = datetime(
            year, int(absolute.group(2)), int(absolute.group(3)), tzinfo=SEOUL
        )
        if absolute.group(1) is None and date_value < now - timedelta(days=180):
            date_value = date_value.replace(year=year + 1)
    elif "모레" in title:
        date_value = (published_at + timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif "내일" in title:
        date_value = (published_at + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif "오늘" in title:
        date_value = published_at.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        coming = re.search(r"(?:오는|다음|이번)\s*(\d{1,2})일", title)
        if coming:
            day = int(coming.group(1))
            year, month = published_at.year, published_at.month
            if day < published_at.day - 7:
                month += 1
                if month == 13:
                    year, month = year + 1, 1
            try:
                date_value = datetime(year, month, day, tzinfo=SEOUL)
            except ValueError:
                return None
        elif allow_bare_day or any(
            keyword in title
            for keyword in (
                "예정",
                "일정",
                "개최",
                "시행",
                "발표",
                "공표",
                "회의",
                "표결",
                "설명회",
                "접수",
                "개막",
                "개봉",
                "공개",
                "발사",
                "경기",
                "출시",
                "정상회담",
                "선거",
            )
        ):
            day_only = re.search(r"(?<!\d)(\d{1,2})일(?!\d)", title)
            if day_only and re.match(
                r"\s*(?:연속|째|간|이하|이상|만에)", title[day_only.end() :]
            ):
                day_only = None
            if day_only:
                day = int(day_only.group(1))
                year, month = published_at.year, published_at.month
                for month_offset in (0, 1):
                    if month_offset == 1 and now - published_at > timedelta(days=14):
                        continue
                    candidate_month = month + month_offset
                    candidate_year = year
                    if candidate_month == 13:
                        candidate_year += 1
                        candidate_month = 1
                    try:
                        candidate = datetime(
                            candidate_year,
                            candidate_month,
                            day,
           …385 tokens truncated… str]] = []
    for cells in _table_rows(document):
        if len(cells) < 3:
            continue
        date_match = re.match(r"(\d{2})\.(\d{2})\.", cells[0])
        time_match = re.match(r"(\d{1,2}):(\d{2})", cells[1])
        if not date_match or not time_match:
            continue
        moment = datetime(
            year,
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(time_match.group(1)),
            int(time_match.group(2)),
            tzinfo=SEOUL,
        )
        result.append((moment, cells[2]))
    return result


def parse_bok_schedules(document: str) -> list[tuple[datetime, str]]:
    result: list[tuple[datetime, str]] = []
    for cells in _table_rows(document):
        if len(cells) < 3:
            continue
        date_match = re.fullmatch(r"(20\d{2})-(\d{2})-(\d{2})", cells[0])
        time_match = re.fullmatch(r"(\d{1,2}):(\d{2})", cells[1])
        if not date_match or not time_match:
            continue
        moment = datetime(
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
            int(time_match.group(1)),
            int(time_match.group(2)),
            tzinfo=SEOUL,
        )
        result.append((moment, cells[2]))
    return result


def _official_schedule_item(
    *,
    title: str,
    scheduled_at: datetime,
    source_name: str,
    source_url: str,
    now: datetime,
    item_type: str = "upcoming",
) -> dict[str, object]:
    category = "증권" if item_type == "stock_calendar" else "경제"
    story = Story(
        title=title,
        link=source_url,
        source=source_name,
        published_at=now,
        summary=f"공식 페이지에 따르면 {scheduled_at.month}월 {scheduled_at.day}일 {scheduled_at.hour:02d}:{scheduled_at.minute:02d}에 발표될 예정입니다.",
    )
    item = _briefing_from_story(
        story,
        category=category,
        item_type=item_type,
        now=now,
        scheduled_at=scheduled_at,
        schedule_status="공식 발표 일정",
    )
    item["importance_score"] = 98.0
    item["confidence"] = 0.99
    return item


def parse_dart(xml_text: str, now: datetime) -> list[dict[str, object]]:
    root = ET.fromstring(xml_text)
    result: list[dict[str, object]] = []
    for item in root.findall("./channel/item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        published = _text(item.find("pubDate"))
        if not title or not link or not published:
            continue
        story = Story(
            title=title,
            link=link,
            source="금융감독원 DART",
            published_at=_parse_rss_date(published),
            summary=f"금융감독원 전자공시시스템에 ‘{title}’ 공시가 게시됐습니다. 세부 수치와 조건은 공시 원문에서 확인할 수 있습니다.",
        )
        result.append(
            _briefing_from_story(
                story, category="증권", item_type="stock_issue", now=now
            )
        )
    return result


def parse_yahoo_market(
    payload: dict[str, Any],
    *,
    symbol: str,
    display_name: str,
    currency: str,
    multiplier: float,
) -> dict[str, object]:
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    current = float(meta.get("regularMarketPrice") or 0) * multiplier
    previous = (
        float(meta.get("previousClose") or meta.get("chartPreviousClose") or 0)
        * multiplier
    )
    if not current or not previous:
        closes = [
            float(value) * multiplier
            for value in result.get("indicators", {})
            .get("quote", [{}])[0]
            .get("close", [])
            if value is not None
        ]
        if len(closes) < 2:
            raise CollectionError(f"market value unavailable: {symbol}")
        previous, current = closes[-2], closes[-1]
    change = current - previous
    observed = datetime.fromtimestamp(
        int(meta.get("regularMarketTime") or result["timestamp"][-1]), timezone.utc
    ).astimezone(SEOUL)
    state = str(meta.get("marketState") or "CLOSED")
    status = "장중 공개값" if state == "REGULAR" else "최근 거래값"
    return {
        "symbol": symbol,
        "display_name": display_name,
        "value": round(current, 4),
        "change": round(change, 4),
        "change_percent": round(change / previous * 100, 4),
        "currency": currency,
        "market_status": status,
        "observed_at": observed.isoformat(),
        "source_name": "Yahoo Finance 공개 차트",
        "is_example": False,
    }


def parse_upbit_market(payload: list[dict[str, Any]]) -> dict[str, object]:
    value = payload[0]
    current = float(value["trade_price"])
    previous = float(value["prev_closing_price"])
    observed = datetime.fromtimestamp(
        int(value["timestamp"]) / 1000, timezone.utc
    ).astimezone(SEOUL)
    return {
        "symbol": "BTC",
        "display_name": "비트코인",
        "value": current,
        "change": current - previous,
        "change_percent": (current - previous) / previous * 100,
        "currency": "KRW",
        "market_status": "24시간 거래값",
        "observed_at": observed.isoformat(),
        "source_name": "업비트 공개 시세",
        "is_example": False,
    }


def _previous_items(
    previous: dict[str, Any] | None, item_type: str, category: str | None = None
) -> list[dict[str, object]]:
    if not previous:
        return []
    return [
        item
        for item in previous.get("briefings", [])
        if item.get("type") == item_type
        and (category is None or item.get("category") == category)
        and not item.get("is_example", False)
    ]


def build_feed(
    now: datetime | None = None,
    *,
    client: HttpClient | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, object]:
    generated_at = (now or datetime.now(SEOUL)).astimezone(SEOUL).replace(microsecond=0)
    client = client or HttpClient()
    health: dict[str, str] = {}
    briefings: list[dict[str, object]] = []

    yonhap_by_category: dict[str, list[Story]] = {
        category: [] for category in CATEGORIES[1:]
    }
    try:
        for story in parse_yonhap_news(client.text(YONHAP_RSS_URL)):
            category = classify_category(story.title)
            if category:
                yonhap_by_category[category].append(story)
        health["yonhap_rss"] = "ok"
    except Exception as error:
        health["yonhap_rss"] = f"failed: {type(error).__name__}"

    for category, query in NEWS_QUERIES.items():
        stories = list(yonhap_by_category[category])
        try:
            url = GOOGLE_NEWS_URL.format(query=quote_plus(f"{query} when:7d"))
            stories.extend(parse_google_news(client.text(url)))
            health[f"news_{category}"] = "ok"
        except Exception as error:
            health[f"news_{category}"] = f"failed: {type(error).__name__}"
        fresh_items = [
            _briefing_from_story(
                story, category=category, item_type="past", now=generated_at
            )
            for story in stories
            if generated_at - timedelta(days=7)
            <= story.published_at
            <= generated_at + timedelta(minutes=10)
        ]
        fresh_items.sort(
            key=lambda item: (
                float(item["importance_score"]),
                str(item["published_at"]),
            ),
            reverse=True,
        )
        combined = _deduplicate(
            [*fresh_items, *_previous_items(previous, "past", category)]
        )[:24]
        briefings.extend(combined)

    upcoming: list[dict[str, object]] = []
    future_date_terms = " OR ".join(
        f'"{moment.month}월 {moment.day}일" OR "{moment.day}일"'
        for moment in (generated_at + timedelta(days=offset) for offset in range(1, 8))
    )
    for category, query in SCHEDULE_QUERIES.items():
        try:
            dated_query = f"{NEWS_QUERIES[category]} ({future_date_terms})"
            url = GOOGLE_NEWS_URL.format(
                query=quote_plus(f"({query}) OR ({dated_query}) when:30d")
            )
            for story in parse_google_news(client.text(url)):
                event = _find_event_time(
                    story.title,
                    story.published_at,
                    generated_at,
                    allow_bare_day=True,
                )
                if not event:
                    continue
                moment, time_confirmed = event
                upcoming.append(
                    _briefing_from_story(
                        story,
                        category=category,
                        item_type="upcoming",
                        now=generated_at,
                        scheduled_at=moment,
                        time_confirmed=time_confirmed,
                        schedule_status="보도된 예정 일정"
                        if time_confirmed
                        else "날짜 확인·시각 미정",
                    )
                )
            health[f"schedule_{category}"] = "ok"
        except Exception as error:
            health[f"schedule_{category}"] = f"failed: {type(error).__name__}"

    official_schedule_items: list[dict[str, object]] = []
    for source_name, source_url, parser in (
        (
            "국가데이터처 보도계획",
            KOSTAT_SCHEDULE_URL.format(month=generated_at.month),
            lambda document: parse_kostat_schedules(document, generated_at.year),
        ),
        (
            "한국은행 통계공표일정",
            BOK_SCHEDULE_URL.format(year=generated_at.year, month=generated_at.month),
            parse_bok_schedules,
        ),
    ):
        key = "kostat_schedule" if source_name.startswith("국가") else "bok_schedule"
        try:
            for moment, title in parser(client.text(source_url)):
                if generated_at <= moment <= generated_at + timedelta(days=7):
                    official_schedule_items.append(
                        _official_schedule_item(
                            title=title,
                            scheduled_at=moment,
                            source_name=source_name,
                            source_url=source_url,
                            now=generated_at,
                        )
                    )
            health[key] = "ok"
        except Exception as error:
            health[key] = f"failed: {type(error).__name__}"

    upcoming = _deduplicate(
        [
            *official_schedule_items,
            *upcoming,
            *_previous_items(previous, "upcoming"),
        ]
    )
    upcoming = [
        item
        for item in upcoming
        if generated_at
        <= datetime.fromisoformat(str(item["scheduled_at"]))
        <= generated_at + timedelta(days=7)
    ]
    upcoming.sort(key=lambda item: str(item["scheduled_at"]))
    upcoming = [
        item
        for category in CATEGORIES[1:]
        for item in [entry for entry in upcoming if entry["category"] == category][:8]
    ]
    upcoming.sort(key=lambda item: str(item["scheduled_at"]))
    briefings.extend(upcoming)

    stock_issues: list[dict[str, object]] = []
    today_start = generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    try:
        query = (
            "(증시 OR 주식 OR 코스피 OR 코스닥 OR 공시) "
            f"after:{(yesterday_start - timedelta(days=1)).date().isoformat()} "
            f"before:{yesterday_start.date().isoformat()}"
        )
        url = GOOGLE_NEWS_URL.format(query=quote_plus(query))
        for story in parse_google_news(client.text(url)):
            if yesterday_start <= story.published_at < today_start:
                stock_issues.append(
                    _briefing_from_story(
                        story,
                        category="증권",
                        item_type="stock_issue",
                        now=generated_at,
                    )
                )
        health["stock_news_yesterday"] = "ok"
    except Exception as error:
        health["stock_news_yesterday"] = f"failed: {type(error).__name__}"

    try:
        dart_items = parse_dart(client.text(DART_RSS_URL), generated_at)
        stock_issues.extend(
            item
            for item in dart_items
            if yesterday_start
            <= datetime.fromisoformat(str(item["published_at"]))
            < today_start
        )
        health["dart_rss"] = "ok"
    except Exception as error:
        health["dart_rss"] = f"failed: {type(error).__name__}"
    stock_issues = _deduplicate(
        [
            *stock_issues,
            *[
                {
                    **item,
                    "id": _stable_id("stock_issue", str(item["source_url"])),
                    "type": "stock_issue",
                }
                for item in briefings
                if item.get("type") == "past"
                and item.get("category") == "증권"
                and yesterday_start
                <= datetime.fromisoformat(str(item["published_at"]))
                < today_start
            ],
            *[
                item
                for item in _previous_items(previous, "stock_issue")
                if yesterday_start
                <= datetime.fromisoformat(str(item["published_at"]))
                < today_start
            ],
        ]
    )[:12]
    briefings.extend(stock_issues)

    stock_calendar = [
        _official_schedule_item(
            title=str(item["title"]),
            scheduled_at=datetime.fromisoformat(str(item["scheduled_at"])),
            source_name=str(item["source_name"]),
            source_url=str(item["source_url"]),
            now=generated_at,
            item_type="stock_calendar",
        )
        for item in official_schedule_items
    ]
    stock_calendar.extend(
        {
            **item,
            "id": _stable_id(
                "stock_calendar", str(item["source_url"]), str(item["scheduled_at"])
            ),
            "type": "stock_calendar",
            "category": "증권",
            "impact": IMPACT_TEXT["증권"],
            "ai_comment": COMMENT_TEXT["증권"],
        }
        for item in upcoming
        if item.get("category") in {"경제", "증권", "산업"}
    )
    stock_calendar = _deduplicate(
        [*stock_calendar, *_previous_items(previous, "stock_calendar")]
    )
    stock_calendar = [
        item
        for item in stock_calendar
        if generated_at
        <= datetime.fromisoformat(str(item["scheduled_at"]))
        <= generated_at + timedelta(days=7)
    ][:12]
    briefings.extend(stock_calendar)

    markets: list[dict[str, object]] = []
    for symbol, display_name, yahoo_symbol, currency, multiplier in MARKET_SYMBOLS:
        try:
            url = (
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{quote_plus(yahoo_symbol)}?range=5d&interval=1d"
            )
            markets.append(
                parse_yahoo_market(
                    client.json(url),
                    symbol=symbol,
                    display_name=display_name,
                    currency=currency,
                    multiplier=multiplier,
                )
            )
            health[f"market_{symbol}"] = "ok"
        except Exception as error:
            health[f"market_{symbol}"] = f"failed: {type(error).__name__}"
    try:
        markets.append(
            parse_upbit_market(
                client.json("https://api.upbit.com/v1/ticker?markets=KRW-BTC")
            )
        )
        health["market_BTC"] = "ok"
    except Exception as error:
        health["market_BTC"] = f"failed: {type(error).__name__}"

    previous_markets = {
        item["symbol"]: item
        for item in (previous or {}).get("markets", [])
        if not item.get("is_example", False)
    }
    current_symbols = {item["symbol"] for item in markets}
    markets.extend(
        item
        for symbol, item in previous_markets.items()
        if symbol not in current_symbols
    )

    failed_sources = sum(value != "ok" for value in health.values())
    feed: dict[str, object] = {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "content_updated_at": generated_at.isoformat(),
        "timezone": "Asia/Seoul",
        "is_example": False,
        "notice": (
            "공개 RSS·공식 일정·공개 시장 데이터를 자동 정리했습니다. 기사 세부 내용과 일정 변경은 원문에서 다시 확인해 주세요."
            if failed_sources == 0
            else f"실제 데이터로 구성했으며 {failed_sources}개 공급원은 일시 실패해 이용 가능한 최신 항목만 표시합니다."
        ),
        "categories": CATEGORIES,
        "briefings": _deduplicate(briefings),
        "markets": markets,
        "source_health": health,
    }
    validate_feed(feed)
    return feed


def validate_feed(feed: dict[str, Any]) -> None:
    if feed.get("schema_version") != 1 or feed.get("is_example") is not False:
        raise ValueError("feed must be schema v1 real data")
    briefings = feed.get("briefings")
    markets = feed.get("markets")
    if not isinstance(briefings, list) or not isinstance(markets, list):
        raise ValueError("briefings and markets must be lists")
    if any(item.get("is_example") for item in briefings + markets):
        raise ValueError("example data cannot enter the production feed")
    if any("example.com" in str(item.get("source_url", "")) for item in briefings):
        raise ValueError("placeholder source URL found")
    past_categories = {
        category: sum(
            item.get("type") == "past" and item.get("category") == category
            for item in briefings
        )
        for category in CATEGORIES[1:]
    }
    missing = [category for category, count in past_categories.items() if count < 4]
    if missing:
        raise ValueError(f"not enough real news for categories: {', '.join(missing)}")
    if len(markets) < 6:
        raise ValueError("not enough real market snapshots")
    if not any(item.get("type") == "upcoming" for item in briefings):
        raise ValueError("no verified future schedule found")
    if not any(item.get("type") == "stock_issue" for item in briefings):
        raise ValueError("no stock issue found")
    if not any(item.get("type") == "stock_calendar" for item in briefings):
        raise ValueError("no stock calendar found")


def _load_previous(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if value.get("is_example") is False else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect the ABO real static JSON feed"
    )
    parser.add_argument("--output", default="public/data/briefing.json")
    parser.add_argument("--previous", help="last successfully deployed feed")
    args = parser.parse_args()
    output = Path(args.output)
    previous = _load_previous(args.previous) or _load_previous(args.output)
    feed = build_feed(previous=previous)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for item in feed["briefings"]:
        counts[str(item["type"])] = counts.get(str(item["type"]), 0) + 1
    print(
        f"Generated {output} ({output.stat().st_size} bytes): {counts}, markets={len(feed['markets'])}"
    )


if __name__ == "__main__":
    main()

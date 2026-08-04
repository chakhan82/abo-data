from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
CATEGORY_THEMES = {
    "사회": ["교통 안전", "응급 의료", "돌봄 지원", "재난 대응"],
    "경제": ["물가 동향", "수출 흐름", "소비 심리", "지역 경제"],
    "산업": ["미래차 공급망", "스마트공장", "배터리 소재", "조선업 인력"],
    "증권": ["시장 수급", "상장사 공시", "지수 변경", "투자자 보호"],
    "부동산": ["주택 가격", "전월세 거래", "정비사업", "주택 공급"],
    "과학·기술": ["인공지능", "우주 산업", "양자 기술", "사이버 보안"],
    "교육": ["학교 안전", "대학 연구", "돌봄 교육", "직업 교육"],
    "국제": ["통상 협의", "원자재 수급", "기후 협력", "해외 정책"],
    "정치": ["국회 안건", "민생 대책", "행정 제도", "예산 점검"],
    "문화": ["문화예술 지원", "국가유산", "콘텐츠 수출", "공연 안전"],
    "스포츠": ["프로리그", "국가대표", "생활체육", "국제대회"],
}


def briefing(
    *,
    item_id: str,
    item_type: str,
    category: str,
    title: str,
    summary: str,
    comment: str,
    impact: str,
    score: float,
    event_time: datetime,
    generated_at: datetime,
    schedule_status: str | None = None,
    keywords: list[str] | None = None,
    companies: list[str] | None = None,
) -> dict[str, object]:
    is_future = item_type in {"upcoming", "stock_calendar"}
    return {
        "id": item_id,
        "type": item_type,
        "category": category,
        "title": title,
        "summary": summary,
        "ai_comment": comment,
        "impact": impact,
        "importance_score": score,
        "published_at": None if is_future else event_time.isoformat(),
        "scheduled_at": event_time.isoformat() if is_future else None,
        "source_name": "ABO GitHub 데모 데이터",
        "source_url": "https://example.com/abo/sample",
        "related_keywords": keywords or [category, "예시"],
        "related_companies": companies or [],
        "schedule_status": schedule_status if is_future else None,
        "source_count": 1,
        "confidence": 0.9,
        "is_example": True,
        "created_at": generated_at.isoformat(),
        "updated_at": generated_at.isoformat(),
    }


def market(
    symbol: str,
    display_name: str,
    value: float,
    change: float,
    change_percent: float,
    currency: str,
    generated_at: datetime,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "display_name": display_name,
        "value": value,
        "change": change,
        "change_percent": change_percent,
        "currency": currency,
        "market_status": "예시 기준값",
        "observed_at": generated_at.isoformat(),
        "source_name": "ABO GitHub 데모 시세",
        "is_example": True,
    }


def build_feed(now: datetime | None = None) -> dict[str, object]:
    generated_at = (now or datetime.now(SEOUL)).replace(microsecond=0)
    items: list[dict[str, object]] = []

    for category_index, (category, themes) in enumerate(CATEGORY_THEMES.items()):
        for position, theme in enumerate(themes):
            past_hours = 3 + category_index % 4 if position == 0 else 24 + category_index * 8 + position * 5
            future_hours = 4 + category_index % 4 if position == 0 else 24 + category_index * 8 + position * 5
            items.append(
                briefing(
                    item_id=f"past-{category_index + 1}-{position + 1}",
                    item_type="past",
                    category=category,
                    title=f"{theme} 주요 내용 공개",
                    summary=f"{theme} 관련 주요 내용과 후속 조치를 확인할 수 있는 예시 브리핑입니다.",
                    comment="예시 데이터입니다. 실제 서비스에서는 원문과 후속 보도를 교차 확인합니다.",
                    impact=f"{category} 분야 후속 영향",
                    score=95 - category_index - position,
                    event_time=generated_at - timedelta(hours=past_hours),
                    generated_at=generated_at,
                    keywords=[category, theme, "예시"],
                )
            )
            items.append(
                briefing(
                    item_id=f"upcoming-{category_index + 1}-{position + 1}",
                    item_type="upcoming",
                    category=category,
                    title=f"{theme} 관련 일정 안내",
                    summary=f"{theme} 관련 세부 일정이 안내될 예정인 예시 브리핑입니다.",
                    comment="예시 일정입니다. 실제 서비스에서는 주최 기관의 변경 공지를 다시 확인합니다.",
                    impact=f"{category} 분야 예정 영향",
                    score=94 - category_index - position,
                    event_time=generated_at + timedelta(hours=future_hours),
                    generated_at=generated_at,
                    schedule_status="예정 일정",
                    keywords=[category, theme, "예시"],
                )
            )

    stock_issues = [
        ("반도체 대형주 중심 거래대금 증가", "반도체", ["삼성전자", "SK하이닉스"]),
        ("외국인 순매수 전환", "외국인 수급", ["코스피 대형주"]),
        ("바이오 업종 공시별 차별화", "바이오 공시", ["바이오 업종"]),
        ("환율 변화에 수출주 변동성 확대", "환율", ["자동차", "부품"]),
    ]
    for position, (title, keyword, companies) in enumerate(stock_issues):
        items.append(
            briefing(
                item_id=f"stock-issue-{position + 1}",
                item_type="stock_issue",
                category="증권",
                title=title,
                summary=f"{title} 흐름을 설명하기 위한 시장 예시 데이터입니다.",
                comment="실제 투자 판단에는 공시 원문과 최신 시세를 별도로 확인해야 합니다.",
                impact="시장 수급 영향",
                score=96 - position * 3,
                event_time=generated_at - timedelta(hours=23 + position * 2),
                generated_at=generated_at,
                keywords=[keyword, "예시"],
                companies=companies,
            )
        )

    stock_calendar = ["국내 대표 IT 기업 실적 발표", "미국 고용지표 발표", "신규 상장사 거래 개시", "배터리 산업 정책 간담회"]
    for position, title in enumerate(stock_calendar):
        items.append(
            briefing(
                item_id=f"stock-calendar-{position + 1}",
                item_type="stock_calendar",
                category="증권",
                title=title,
                summary=f"{title}을 가정한 예시 일정입니다.",
                comment="실제 일정은 거래소·공시·주최 기관 자료로 다시 확인해야 합니다.",
                impact="국내외 증시 영향",
                score=98 - position * 3,
                event_time=generated_at + timedelta(hours=4 + position * 5),
                generated_at=generated_at,
                schedule_status="예정 일정",
                keywords=["증권", "일정", "예시"],
            )
        )

    markets = [
        market("USDKRW", "원/달러", 1372.40, -3.20, -0.23, "KRW", generated_at),
        market("JPYKRW", "원/엔(100엔)", 932.18, 2.11, 0.23, "KRW", generated_at),
        market("EURKRW", "원/유로", 1491.72, -1.45, -0.10, "KRW", generated_at),
        market("KOSPI", "코스피", 2786.31, 18.42, 0.67, "pt", generated_at),
        market("KOSDAQ", "코스닥", 862.55, -2.18, -0.25, "pt", generated_at),
        market("DJI", "다우존스", 41240.52, 112.30, 0.27, "pt", generated_at),
        market("IXIC", "나스닥", 17781.12, 95.10, 0.54, "pt", generated_at),
        market("SPX", "S&P 500", 5463.54, 18.01, 0.33, "pt", generated_at),
        market("WTI", "국제유가(WTI)", 76.82, -0.41, -0.53, "USD", generated_at),
        market("GOLD", "금", 2418.60, 8.20, 0.34, "USD", generated_at),
        market("BTC", "비트코인", 93850000, 1240000, 1.34, "KRW", generated_at),
    ]
    return {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "timezone": "Asia/Seoul",
        "is_example": True,
        "notice": "현재 모든 콘텐츠는 앱 동작 검증용 예시 데이터입니다.",
        "categories": CATEGORIES,
        "briefings": items,
        "markets": markets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the ABO static JSON feed")
    parser.add_argument("--output", default="public/data/briefing.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_feed(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

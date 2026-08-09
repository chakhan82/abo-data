from __future__ import annotations

import argparse
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")
WIDGET_SIZE = (170, 170)
SCALE = 2


@dataclass(frozen=True)
class WidgetCategory:
    name: str
    slug: str
    color: str


CATEGORIES = (
    WidgetCategory("경제", "economy", "#2563EB"),
    WidgetCategory("산업", "industry", "#0F766E"),
    WidgetCategory("증권", "securities", "#B45309"),
    WidgetCategory("국제", "international", "#7C3AED"),
)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SEOUL)
    return parsed.astimezone(SEOUL)


def _normalized_title(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def select_top_news(feed: dict[str, Any], category: str) -> list[dict[str, Any]]:
    generated_at = _parse_time(feed.get("generated_at")) or datetime.now(SEOUL)
    fallback_boundary = generated_at - timedelta(days=7)
    candidates: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for raw_item in feed.get("briefings", []):
        if not isinstance(raw_item, dict):
            continue
        if raw_item.get("type") != "past" or raw_item.get("category") != category:
            continue
        published_at = _parse_time(raw_item.get("published_at"))
        if published_at is None or published_at < fallback_boundary:
            continue
        title = str(raw_item.get("title") or "").strip()
        normalized = _normalized_title(title)
        if not normalized or normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        item = dict(raw_item)
        item["_published_at"] = published_at
        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            float(item.get("importance_score") or 0),
            int(item.get("source_count") or 1),
            item["_published_at"],
        ),
        reverse=True,
    )
    return candidates[:4]


def _font_candidates(*, bold: bool) -> list[Path]:
    configured = os.environ.get("ABO_WIDGET_FONT_BOLD" if bold else "ABO_WIDGET_FONT")
    names = [
        configured,
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        if bold
        else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
        if bold
        else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    return [Path(name) for name in names if name]


def _font(
    size: int, *, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates(bold=bold):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size * SCALE)
    return ImageFont.load_default(size=size * SCALE)


def _scaled_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(value * SCALE for value in box)


def _text_width(
    draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), value, font=font)
    return right - left


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    font: ImageFont.ImageFont,
    *,
    max_width: int,
    max_lines: int,
) -> list[str]:
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return ["새 소식을 확인 중입니다"]
    lines: list[str] = []
    remaining = text
    pixel_width = max_width * SCALE

    while remaining and len(lines) < max_lines:
        fitting = ""
        for char in remaining:
            candidate = fitting + char
            if _text_width(draw, candidate, font) > pixel_width:
                break
            fitting = candidate
        if not fitting:
            fitting = remaining[0]
        split_at = fitting.rfind(" ")
        if split_at > len(fitting) // 2 and len(fitting) < len(remaining):
            fitting = fitting[:split_at]
        lines.append(fitting.strip())
        remaining = remaining[len(fitting) :].lstrip()

    if remaining and lines:
        ellipsis = "…"
        last = lines[-1]
        while last and _text_width(draw, last + ellipsis, font) > pixel_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + ellipsis
    return lines


def _relative_time(published_at: datetime | None, generated_at: datetime) -> str:
    if published_at is None:
        return "시각 확인"
    minutes = max(0, int((generated_at - published_at).total_seconds() // 60))
    if minutes < 1:
        return "방금 전"
    if minutes < 60:
        return f"{minutes}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    return f"{hours // 24}일 전"


def render_widget_png(
    feed: dict[str, Any],
    category: WidgetCategory,
    items: list[dict[str, Any]],
    output_path: Path,
) -> None:
    generated_at = _parse_time(feed.get("generated_at")) or datetime.now(SEOUL)
    canvas = Image.new(
        "RGB", (WIDGET_SIZE[0] * SCALE, WIDGET_SIZE[1] * SCALE), "#F8FAFC"
    )
    draw = ImageDraw.Draw(canvas)
    regular = _font(9)
    small = _font(7)
    headline = _font(9, bold=True)
    header = _font(13, bold=True)
    rank_font = _font(9, bold=True)

    draw.rounded_rectangle(
        _scaled_box((1, 1, 169, 169)),
        radius=11 * SCALE,
        fill="#FFFFFF",
        outline="#D8DEE9",
        width=1 * SCALE,
    )
    draw.rounded_rectangle(
        _scaled_box((1, 1, 169, 34)), radius=11 * SCALE, fill=category.color
    )
    draw.rectangle(_scaled_box((1, 23, 169, 34)), fill=category.color)
    draw.text(
        (10 * SCALE, 7 * SCALE), f"ABO {category.name}", font=header, fill="#FFFFFF"
    )
    draw.text(
        (10 * SCALE, 24 * SCALE),
        f"실시간 인기 뉴스 · {generated_at:%m.%d %H:%M}",
        font=small,
        fill="#EAF0FF",
    )

    for index in range(2):
        top = 40 + index * 53
        bottom = top + 48
        draw.rounded_rectangle(
            _scaled_box((7, top, 163, bottom)), radius=7 * SCALE, fill="#F8FAFC"
        )
        draw.ellipse(_scaled_box((12, top + 5, 32, top + 25)), fill=category.color)
        rank = str(index + 1)
        rank_box = draw.textbbox((0, 0), rank, font=rank_font)
        rank_width = rank_box[2] - rank_box[0]
        draw.text(
            ((22 * SCALE) - rank_width / 2, (top + 8) * SCALE),
            rank,
            font=rank_font,
            fill="#FFFFFF",
        )

        item = items[index] if index < len(items) else {}
        lines = _wrap_lines(
            draw,
            str(item.get("title") or "새 소식을 확인 중입니다"),
            headline,
            max_width=121,
            max_lines=2,
        )
        for line_index, line in enumerate(lines):
            draw.text(
                (37 * SCALE, (top + 4 + line_index * 13) * SCALE),
                line,
                font=headline,
                fill="#172033",
            )
        source = str(item.get("source_name") or "ABO")
        source_count = int(item.get("source_count") or 1)
        coverage = f" · 매체 {source_count}곳" if source_count > 1 else ""
        meta = f"{source} · {_relative_time(item.get('_published_at'), generated_at)}{coverage}"
        meta_line = _wrap_lines(draw, meta, small, max_width=121, max_lines=1)[0]
        draw.text(
            (37 * SCALE, (top + 32) * SCALE), meta_line, font=small, fill="#667085"
        )

    draw.line(_scaled_box((9, 146, 161, 146)), fill="#E5E7EB", width=1 * SCALE)
    footer = "클릭하면 TOP4 자세히 보기"
    footer_width = _text_width(draw, footer, regular)
    draw.text(
        ((170 * SCALE - footer_width) / 2, 153 * SCALE),
        footer,
        font=regular,
        fill=category.color,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.resize(WIDGET_SIZE, Image.Resampling.LANCZOS).save(
        output_path, format="PNG", optimize=True
    )


def _item_time(item: dict[str, Any]) -> str:
    published_at = item.get("_published_at")
    return (
        published_at.strftime("%Y.%m.%d %H:%M")
        if isinstance(published_at, datetime)
        else "시각 확인"
    )


def render_detail_html(
    feed: dict[str, Any],
    category: WidgetCategory,
    items: list[dict[str, Any]],
    output_path: Path,
) -> None:
    generated_at = _parse_time(feed.get("generated_at")) or datetime.now(SEOUL)
    cards = []
    for index, item in enumerate(items, start=1):
        title = html.escape(str(item.get("title") or "제목 없음"))
        summary = html.escape(str(item.get("summary") or ""))
        source = html.escape(str(item.get("source_name") or "출처 확인"))
        url = html.escape(str(item.get("source_url") or "#"), quote=True)
        source_count = int(item.get("source_count") or 1)
        cards.append(
            f"""<article class="news-card">
  <div class="rank" style="background:{category.color}">{index}</div>
  <div class="news-body">
    <h2>{title}</h2>
    <p>{summary}</p>
    <div class="meta">{source} · {_item_time(item)} · 매체 {source_count}곳</div>
    <a href="{url}" target="_blank" rel="noopener noreferrer">원문 보기</a>
  </div>
</article>"""
        )
    if not cards:
        cards.append('<p class="empty">현재 표시할 뉴스가 없습니다.</p>')

    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="1800">
  <title>ABO {html.escape(category.name)} 실시간 인기 뉴스 TOP4</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f4f6fa; color: #172033; font-family: "Noto Sans KR", "Malgun Gothic", sans-serif; }}
    main {{ width: min(720px, calc(100% - 24px)); margin: 24px auto 48px; }}
    header {{ padding: 24px; border-radius: 18px; color: white; background: linear-gradient(135deg, {category.color}, #172033); }}
    h1 {{ margin: 0 0 7px; font-size: 25px; }}
    header p {{ margin: 0; opacity: .88; font-size: 14px; }}
    .news-list {{ display: grid; gap: 12px; margin-top: 16px; }}
    .news-card {{ display: flex; gap: 13px; padding: 17px; border: 1px solid #e0e5ee; border-radius: 15px; background: white; box-shadow: 0 5px 16px rgba(25,35,55,.05); }}
    .rank {{ display: grid; place-items: center; flex: 0 0 32px; height: 32px; border-radius: 10px; color: white; font-weight: 800; }}
    .news-body {{ min-width: 0; }}
    h2 {{ margin: 1px 0 8px; font-size: 17px; line-height: 1.42; }}
    .news-body p {{ margin: 0 0 10px; color: #4b5565; font-size: 14px; line-height: 1.55; }}
    .meta {{ color: #7a8495; font-size: 12px; }}
    a {{ display: inline-block; margin-top: 11px; color: {category.color}; font-size: 13px; font-weight: 700; text-decoration: none; }}
    .notice {{ margin-top: 18px; color: #697386; font-size: 12px; line-height: 1.55; }}
    .empty {{ padding: 25px; border-radius: 15px; background: white; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>ABO {html.escape(category.name)} 실시간 인기 뉴스 TOP4</h1>
      <p>AI가 전하는 오늘의 핵심 브리핑 · {generated_at:%Y.%m.%d %H:%M} 기준</p>
    </header>
    <section class="news-list">{"".join(cards)}</section>
    <p class="notice">공개된 제목과 게시 시각, 복수 매체 보도 및 중요도를 기준으로 정리합니다. 자세한 내용은 원문에서 확인해 주세요.</p>
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def render_all(feed_path: Path, output_dir: Path) -> None:
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    for category in CATEGORIES:
        items = select_top_news(feed, category.name)
        render_widget_png(feed, category, items, output_dir / f"{category.slug}.png")
        render_detail_html(feed, category, items, output_dir / f"{category.slug}.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="ABO 네이버 블로그 뉴스 위젯 생성기")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render_all(args.input, args.output)


if __name__ == "__main__":
    main()

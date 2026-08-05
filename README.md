# ABO Data

AI Briefing On Android 앱이 읽는 실제 공개 데이터를 GitHub Pages의 정적 JSON으로 배포합니다. 뉴스는 30분마다 최신성·복수 매체 보도·중요도를 다시 계산해 전체·분야별 실시간 인기 TOP4로 제공하고, 최신 주식 보도의 검색어 TOP5도 함께 집계합니다.

- `collector.py`: 공개 RSS, 공식 발표 일정, 공개 시장값 수집기
- `public/data/briefing.json`: 앱이 읽는 단일 JSON
- `public/app/version.json`: 앱이 확인하는 최신 APK 버전과 다운로드 주소
- `.github/workflows/publish.yml`: 30분 간격 수집·검증·Pages 배포
- `tests/`: 파서와 운영 피드 계약 검사

## 공급원

- 뉴스: 연합뉴스 공식 RSS, Google 뉴스 RSS 검색 결과
- 기업 공시: 금융감독원 DART 오늘의 공시 RSS
- 확인된 일정: 국가데이터처 월간 보도계획, 한국은행 통계공표일정, 11개 분야별로 향후 7일의 날짜가 확인된 공개 보도
- 금융시장: Yahoo Finance 공개 차트, 업비트 공개 시세

기사 전문을 저장하지 않습니다. 제목, 짧은 핵심 정리, 게시·예정 시각, 출처와 원문 링크만 제공합니다. 일정은 공식 페이지 또는 공개 제목에서 미래 날짜를 확인할 수 있을 때만 포함하며, 시각이 없는 일정은 `날짜 확인·시각 미정`으로 표시합니다. 자동 정리는 사실관계가 바뀔 수 있으므로 중요한 판단 전 원문을 확인해야 합니다.

## 장애 처리

워크플로는 수집 전에 현재 Pages 피드를 내려받습니다. 일부 공급원이 실패하면 이용 가능한 최신 실제 항목을 보충하되 예시값이나 가짜 일정을 만들지 않습니다. 검증을 통과하지 못한 실행은 배포되지 않으므로 Pages에는 마지막 정상 데이터가 유지됩니다.

## 로컬 실행

```bash
python collector.py --previous public/data/briefing.json --output public/data/briefing.json
python -m unittest discover -s tests -v
```

## GitHub Pages 주소

```text
https://chakhan82.github.io/abo-data/data/briefing.json
```

```text
https://chakhan82.github.io/abo-data/app/version.json
```

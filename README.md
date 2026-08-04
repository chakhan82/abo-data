# ABO Data

AI Briefing On Android 앱이 읽는 공개 정적 JSON을 GitHub Pages로 배포하는 저장소입니다.

- `collector.py`: `Asia/Seoul` 기준 데이터 생성기
- `public/data/briefing.json`: 앱이 읽는 단일 JSON
- `.github/workflows/publish.yml`: 30분 간격 생성·검증·Pages 배포
- `tests/`: 분야별 TOP4와 필수 섹션 계약 검사

현재 수집기는 앱 기능 검증용 예시 데이터를 만들며 모든 항목에 `is_example=true`를 설정합니다. 실제 뉴스, 일정, 시세 공급자를 연결하기 전에는 서비스 데이터로 오인하면 안 됩니다.

## 로컬 실행

```bash
python collector.py --output public/data/briefing.json
python -m unittest discover -s tests -v
```

## GitHub Pages 주소

저장소 이름을 `abo-data`로 만들고 Pages의 배포 원본을 GitHub Actions로 지정하면 다음 주소를 사용합니다.

```text
https://chakhan82.github.io/abo-data/data/briefing.json
```

# ABO 자동 갱신 신뢰성 설계

## 의도

GitHub Actions 예약 호출 누락과 수집·배포 내부 실패를 분리해 관측하고, 기존 앱·뉴스 수집·블로그 위젯·GitHub Pages 주소를 유지하면서 실제 공개 데이터가 30분 주기에 가깝게 갱신되도록 한다.

## 확인된 원인

- `7,37 * * * *` 예약은 2026-10-26 UTC에 기대한 48회 중 5회만 실행을 생성했다. 생성된 실행은 즉시 시작해 성공했으므로 주된 공백은 GitHub 예약 이벤트 누락이다.
- 매 실행의 `apt-get install fonts-noto-cjk`가 61.2MB를 내려받으며 한 실행에서 8분 이상 지연됐다.
- 수집기는 공급원 실패 시 이전 항목을 섞지만 재사용 사실을 기록하지 않는다.
- `content_updated_at`은 실질 콘텐츠가 같은 경우에도 매 실행 시각으로 덮어쓴다.
- 배포 성공 여부와 공개 JSON·위젯이 해당 실행 결과인지가 별도로 검증되지 않는다.

## 목표

- 기존 JSON 필드와 Pages 경로를 깨지 않고 실행·공급원 상태 메타데이터를 추가한다.
- 재사용한 콘텐츠의 항목 갱신 시각을 보존하고 실질 콘텐츠가 같으면 `content_updated_at`을 보존한다.
- 폰트와 pip 다운로드를 캐시하고 모든 외부 다운로드에 재시도와 제한시간을 둔다.
- 중복 실행은 취소하지 않고 직렬화하며, 배포 뒤 공개 산출물의 실행 ID와 해시를 검증한다.
- Cloudflare Worker가 30분마다 데이터 지연을 확인하고 필요한 경우에만 기존 `workflow_dispatch`를 호출하도록 준비한다.

## 비목표

- 뉴스 선정·순위·카테고리·일정 범위 변경
- Android 앱 데이터 모델이나 화면 변경
- 블로그 위젯 크기·디자인·공개 URL 변경
- Cloudflare 계정 생성, 토큰 발급 또는 실제 Worker 배포

## 선택한 접근

기존 GitHub 예약을 주 경로로 유지하고 Cloudflare Cron을 지연 감시 겸 보조 호출로 둔다. 수집 결과에는 하위 호환 가능한 `collection` 메타데이터만 추가하며, 공개 산출물에 배포 매니페스트를 포함해 실행 ID와 SHA-256을 확인한다. GitHub 예약을 완전히 제거하는 방식은 외부 계정 장애가 단일 실패 지점이 되므로 제외했고, GitHub 예약만 유지하는 방식은 확인된 호출 누락을 해결하지 못해 제외했다.

## 데이터 계약

- 기존 최상위 필드와 항목 필드는 유지한다.
- `collection.run_id`, `started_at`, `completed_at`, `trigger`, `run_attempt`, `reused_previous_data`, `sources`를 추가한다.
- `collection.sources.<key>`는 `status`, `error_type`, `reused_previous`를 기록한다.
- 내부 재사용 표시는 출력 전에 제거한다.
- 의미 있는 콘텐츠가 동일하면 이전 `content_updated_at`과 항목 `updated_at`을 유지한다.

## 배포 및 감시

- `public/deployment-manifest.json`은 실행 ID와 JSON·4개 위젯 HTML/PNG의 SHA-256을 기록한다.
- Pages 배포 후 검증 스크립트가 캐시 무효화 쿼리로 매니페스트와 각 공개 파일을 재다운로드해 실행 ID와 해시를 비교한다.
- Cloudflare Worker는 공개 JSON의 `collection.completed_at`을 확인하고, 임계치 초과 시 진행 중/대기 중 GitHub 실행이 없는 경우에만 `workflow_dispatch`를 호출한다.

## 외부 설정

- Cloudflare Worker 계정
- 대상 저장소로 한정한 GitHub fine-grained PAT (`Actions: write`)
- Worker secret `GITHUB_TOKEN`
- 선택 사항인 지연 알림용 `ALERT_WEBHOOK_URL`


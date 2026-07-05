# App — Cyber Defense Readiness Simulator (frontend)

> 티켓: A-01 ~ A-06 (Training Mode) · A-07 ~ A-11 (Operations Mode, mock 계약 기준)
> 담당: 한지훈
> 기준 계약: `../architecture/API_SPEC.md`

`wireframes/service-wireframe.html`의 6개 화면을 실제 라우팅 앱으로 재구성한 프론트엔드다. 빌드 도구가 필요 없는 vanilla HTML/CSS/JS로 작성되어, 파일을 직접 열어도, 정적 서버로 띄워도 동작한다.

## 실행

```bash
# 방법 1: 정적 서버 (권장)
cd app
python3 -m http.server 5173
# 브라우저에서 http://127.0.0.1:5173 열기

# 방법 2: 파일 직접 열기
# app/index.html 을 브라우저로 더블클릭
```

첫 화면은 훈련 홈이다. `훈련 시작 -> 시나리오 선택 -> 임무 브리핑 -> (임무 시작) 미션 데스크 -> 사후 강평` 순서로 이동한다.
각 주요 화면은 진입 시 현재 화면에서 먼저 볼 곳과 눌러야 할 곳을 coach mark로 자동 안내한다. 우측 `가이드` 버튼으로 닫은 투어를 다시 시작할 수 있다.

## 라우트

| 해시 | 화면 | 상태 |
|---|---|---|
| `#/home` | 01 훈련 홈 | 구현 (전체 API-driven: 헤드라인·추천·숙련도·최근 사후 강평·진행률·공통 약점) |
| `#/scenarios` | 02 시나리오 선택 | 구현 (API 연동, 난이도 필터 유지·건수 표시) |
| `#/briefing/:scenarioId` | 03 임무 브리핑 | 구현 (API 연동, 난이도/시간 표시, 임무 시작→세션 생성) |
| `#/mission/:sessionId` | 04/05 미션 데스크 | 구현 (상황 피드 polling · 4개 장비 탭(UTM/FW·NAC·지시사항·ThreatIntel) query→view_model · ThreatIntel은 로컬 StealthMole 데이터셋(마스킹) landscape 연동 · 상세 로그 분석 · 차단/격리 조치 제안(승인 대기) · 근거 pin · 조사 노트 · 판단 패널 · 평가 미리보기) |
| `#/aar/:sessionId` | 06 사후 강평 | 구현 (점수/등급 · 조사 타임라인 · 확인/누락 근거 · 동적 평가 피드백 · 다음 훈련 · 운영 보조 케이스 재사용) |
| `#/dashboard` | 사이버 방호 통합 대시보드 | 구현 (방호태세·전파·사건·장비·지식 KPI, 우선 확인 타일, 장비/위협/일정 섹션 · API 대기 상태 포함 자동 가이드) |
| `#/dashboard/equipment` | 보안 장비 상태 | 구현 (UTM/FW·NAC·지시사항함·ThreatIntel adapter read model · API 대기 상태 포함 자동 가이드) |
| `#/dashboard/threats` | 위협 동향 | 구현 (StealthMole masked trend 카드 · API 대기 상태 포함 자동 가이드) |
| `#/dashboard/search` | 통합 검색 | 구현 (사건·상담·사후 강평·수동 지식 검색 · 결과/대기 상태 자동 가이드) |
| `#/ops/incidents` | 상위 조직/하급제대 전파/수신 | 구현 (상황 접수 폼 → 해당·상위 조직 조직 자동 통보(1-1) · 상태별 4컬럼 보드 · 상위 조직 관점 하위 조직 상태판 집계(1-2)) |
| `#/ops/incidents/:id` | 사건 상세 | 구현 (timeline·근거·알림 이력 · 상태 전이는 발생 조직만, needs_approval은 승인 대기 제안·`executed=false`) |
| `#/ops/notifications` | 알림 피드 | 구현 (미확인 우선 · ack · 상위 조직 관점 하위 조직 알림 합류 · 인앱 레코드만) |
| `#/knowledge` | 지식DB | 구현 (키워드/태그/조직 검색 · 지식 카드(출처·근거) · 축적 대시보드 · 사건 종결/문의 해결 시 자동 축적(2-2)) |
| `#/helpdesk` | 헬프데스크 | 구현 (문의 → 검색 기반 답변 · citation 강제 · 근거 없으면 "근거 부족" 반환(환각 방지) · 해결 처리 시 FAQ 지식 축적(2-1)) |
| `#/helpdesk/inbox` | 인입 채팅 | 구현 (문의 채팅 인입 → 자동 분류 → 대응 워크벤치 이동 · 자동 가이드) |
| `#/helpdesk/conversations/:conversationId` | 대응 워크벤치 | 구현 (상담 답변·자동 분류·추천 조치·관련 지식·지식DB 후보 등록 · 오류 상태 자동 가이드) |
| `#/helpdesk/integrations` | 헬프데스크 연동 상태 | 구현 (ChatIngress/UserDirectory/Knowledge Search/LLM API 포트 상태 · 자동 가이드) |

상단 `훈련 모드 / 사이버 방호 대시보드 / 헬프데스크` 탭으로 세 모드를 전환한다. 사이버 방호·헬프데스크 화면은 조직 컨텍스트
(내 조직=조치 수행 / 상위 조직=읽기 전용)를 공유하며, 조직·인원은 synthetic label만 사용한다.
Operations API(B-08~B-12)는 백엔드가 동일 계약으로 제공한다(mock↔live 화면 동일). 지식DB·헬프데스크는
live에서 SQLite 비휘발로 동작하며, 사건 종결·사후 강평·문의 해결이 자동으로 지식에 축적된다.

## API 연결 전환 (mock ↔ 실제 서버)

화면 코드는 API base URL을 모른다. `js/config.js` 한 곳만 바꾸면 전환된다.

```js
// 현재 기본값: 이성진 FastAPI 백엔드에 연결 (통합)
API_BASE: "http://127.0.0.1:8000",

// standalone(정적 파일)로 mock만 쓰려면:
API_BASE: null,
```

- `API_BASE: null` 이면 `js/api/mock.js`의 fixture 응답을 사용한다. 모든 응답은 `API_SPEC.md`의 envelope과 동일하다.
- base URL을 지정하면 같은 경로로 `fetch` 요청을 보낸다. 화면은 그대로 동작한다.
- 상단바 오른쪽 배지가 현재 모드(`fixture` / `live`)를 표시한다.

### 백엔드 통합 연결 방법

```bash
# 1) 백엔드 실행 (레포 루트에서)
uv sync --frozen
uv run uvicorn d4d.api.main:app --host 127.0.0.1 --port 8000

# 2) 프론트 실행 (별도 터미널)
cd app && python3 -m http.server 5173
# 브라우저에서 http://127.0.0.1:5173
```

백엔드는 로컬 origin과 `file://`(Origin: null)에 대해 CORS를 허용한다. mock과 백엔드는
동일한 계약(`query_type`/`action_type`/`view_model`/evidence id)을 공유하므로 두 모드의
화면 렌더 결과가 같다. 장비 `상세 로그 분석`은 백엔드 `equipment/analyze`로 연결된다.

## 구조

```
app/
  index.html            앱 shell (topbar, 좌측 nav, screen container)
  css/styles.css        cyber-ops 톤 디자인 (service-wireframe 토큰 재사용)
  js/
    config.js           API_BASE / mode 설정
    ui.js               HTML escape, 상태 블록, nav 컨트롤러
    store.js            선택 시나리오 / 세션 상태 보관
    api/mock.js         API_SPEC 기반 fixture 응답
    api/client.js       get/post/put, mock↔http 어댑터 분리
    router.js           hash 라우터 (+ 화면 이탈 onLeave 정리 훅)
    screens/            home, scenarios, briefing, missionDesk, aar, ops(Operations 5화면)
    app.js              부트스트랩 (clock, mode badge, 데모 초기화, 라우터 시작)
  tools/safety-scan.js  데모 안전성 스캐너 (자격증명/식별번호/공인 IP 검사)
```

## 검증

- 전 JS 파일 문법 검사 (JavaScriptCore) 통과.
- mock API + client 계약 스모크 11/11 통과 (브리핑에 hidden ground truth 미노출 포함).
- 라우터 패턴 매칭 6/6 통과.
- A-02 API-driven 검증 11/11 통과: 홈 헤드라인/진행률/공통 약점이 응답 기반, 브리핑 난이도·시간 노출, 난이도 필터 0건 처리, 브리핑 응답에 ground truth 키(`ground_truth`/`answer_key`/`expected_severity`) 부재.
- A-03 미션 데스크 검증 27/27 통과: 4개 장비 port 조회가 `evidence[]`+`view_model` 반환, 모든 근거가 sanitized(`raw_available=false`·`redaction` 표기), TrusGuard 테이블/NAC 카드 shape, 잘못된 port는 `BAD_REQUEST`, 이벤트 `since_seq` polling 중복 없음, 피드가 서비스 장애·의심 outbound·지시사항·단말 posture를 모두 포함.
- A-03 상세 분석/조치 제안 안전성 + UI 상호작용 통과: 4개 port 상세 분석이 위험도·신호·연관 근거·상세 반환(ground truth/raw 미노출), `policy_update_request`/`endpoint_isolation_review`는 클라이언트 입력과 무관하게 승인 필요 강제, 어떤 조치도 `executed=false`, 조회→상세 분석→차단 제안→승인 대기 트레이 등록 흐름이 자동 실행 없이 완주.
- A-04 근거 pin/판단/평가 계약 9/9 + UI 흐름 6/6 통과: 없는 근거 pin·인용은 `UNKNOWN_EVIDENCE` 거부, 침해 의심 이상 심각도를 근거 없이 저장하면 `WEAK_SEVERITY_BASIS` 경고, 평가 미리보기에 private rubric detail 미노출, 조회→pin→판단 저장→평가 strip 흐름 완주.
- A-05 사후 강평/운영 재사용 계약·UI 12/12 통과: 생성(POST)→리플레이(GET) 로드, 점수/등급·타임라인(지연 강조)·확인/누락 근거·rubric 피드백 렌더, 운영 재사용이 operator note draft 생성(실 조치 미실행), 없는 근거 재사용·session_id 누락 거부.
- A-06 데모 안전성 스캔 통과(`tools/safety-scan.js`): 14개 소스(ops 포함)에서 자격증명·JWT·private key·마스킹 안 된 식별번호·문서용(RFC5737)/사설(RFC1918)/loopback 외 공인 IP 미검출.
- A-07 Operations 셸 27/27 통과: 모드 전환(body 모드 속성·nav 그룹·탭 활성), ops 라우트 5종 진입, 조직 컨텍스트 전환(내 조직↔상위 조직), units API 미제공 시 synthetic 폴백.
- A-08 접수/알림 28/28 통과: 사건 생성 → 심각도별 전파 깊이(low/medium=직속, high=2단계, critical=전체)로 해당·상위 조직 조직 알림, 미확인 우선 정렬·ack, 상위 조직 관점 하위 조직 알림/사건 합류, 잘못된 심각도·조직·근거 거부.
- A-09 상태 전이 27/27 통과: 발생 조직만 전이(상위 조직은 FORBIDDEN), 상태 머신 위반 거부, needs_approval은 `approval_required`·`executed=false`, 전이 시 상위 조직 status_changed 알림, timeline 비휘발 기록, 상위 조직 상태판 집계.
- A-10/A-11 지식·헬프데스크 36/36 통과: 키워드/태그/조직 검색, 사건 종결 시 자동 축적(+중복 억제), 문의 답변에 citation 강제, 무관한 질문은 "근거 부족"(환각 방지), 해결 처리 시 FAQ 축적.

## 안전 경계

- 모든 표시 데이터는 synthetic/masked fixture다. 하단 고정 배너와 상단 `fixture · synthetic data` 배지로 항상 표시한다.
- 브리핑/시나리오 응답에 hidden ground truth를 포함하지 않는다. 상세 rubric은 사후 강평에서만 공개한다.
- write-like action(정책 반영/격리/계정)은 실행이 아니라 `approval_required` proposal로만 표시하며, 서버(mock)가 해당 유형의 승인 필요를 강제하고 `executed=false`를 보장한다.
- 사용자 식별자는 마스킹(`18-1xxx-7xxx`), IP는 문서용/사설 대역만 사용한다. `tools/safety-scan.js`로 반입 전 자동 점검한다.

## 데모 진행 순서 (약 4~6분)

1. 훈련 홈에서 추천 훈련 `바로 시작` 또는 `훈련 시작`.
2. 시나리오 선택 → 임무 브리핑 → `임무 시작`.
3. 미션 데스크: 상황 피드 확인 → TrusGuard 조회 → `상세 로그 분석` → `차단 정책 제안`(승인 대기 확인) → 근거 `pin` → 판단 저장 → 평가 strip 확인.
4. `대응 종료 · 사후 강평으로 이동` → 점수/타임라인/놓친 근거/피드백 확인.
5. `운영 보조 케이스로 재사용` → operator note draft로 Operations Mode 연결 시연.
6. 좌측 하단 `데모 초기화`로 다음 시연 준비.

## Operations Mode 데모 순서 (약 3~4분, 이어서)

1. 상단 `실제 상황 모드` 탭 클릭 → 상황판 진입 (조직 관점: 보안대대-A).
2. 상황 접수: 제목·심각도(예: 높음) 입력 → `접수 · 자동 통보` → 배너에서 해당·상위 조직 조직 통보 확인 (1-1).
3. `알림 피드`에서 미확인 알림 확인 → `확인`(ack). 조직 관점을 `상위 관제센터`로 바꿔 하위 조직 알림 합류 확인.
4. 사건 카드 클릭 → 사건 상세: `조치 시작` → `승인 필요 조치 상신(제안)`(승인 대기·실행 아님 확인) → `조치 완료` → `종결`. 전이마다 timeline 기록·상위 조직 알림 전파 확인 (1-2).
5. 상위 조직 관점으로 상황판 → `하위 조직 상태판`(읽기 전용) 확인.
6. `지식DB`: 방금 종결한 사건이 자동 축적된 것을 검색으로 확인 (2-2, 담당자 인수인계에도 비휘발).
7. `헬프데스크`: "유해 IP 지시 반영이 일부 누락됐을 때 절차는?" 문의 → 근거 인용 답변 확인 → 무관한 질문으로 "근거 부족"(환각 방지) 확인 → `해결 처리`로 FAQ 지식 축적 (2-1).

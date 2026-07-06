# Parser Celery Queue 도입 계획

> 작성일: 2026-07-06 · 개정: 2026-07-07 (코드 레벨 검증 결과 + 큐 배치 위치 결정 + A/B안 상세 설계 반영)
> 목적: Parser(HWP 변환) 작업을 큐 기반 비동기 작업으로 처리하기 위한 설계 및 구현 계획

## 0. 요약 (TL;DR)

- Langflow의 Celery 인프라는 **골격만 있고 동작하는 경로가 없는 죽은 코드 상태**다 (§1.2에서 코드 근거 확인).
- 큐를 놓을 수 있는 자리는 3곳인데, **컴포넌트 내부는 실행 모델과 충돌하므로 불가**하고,
  나머지 둘 중 **A안(파서 서비스 쪽 큐)을 먼저** 하고 B안(Langflow Job 큐)은 대량 인제스천 요구가 생기면 얹는다.
- A안은 Langflow 코어를 전혀 수정하지 않는다. 번들 컴포넌트만 "제출+폴링" 방식으로 바뀐다
  (참조 구현: `docling_remote.py`의 `_poll_and_fetch_result`).

## 1. 배경

### 1.1 현재 구조

```
API 요청
  └─ get_task_service().fire_and_forget_task(func, ...)
       └─ TaskService (services/task/service.py)
            ├─ celery_enabled=False (기본) → AnyIOBackend
            │    └─ JobQueueService: 같은 프로세스 asyncio 태스크로 실행
            └─ celery_enabled=True → CeleryBackend
                 └─ task_func.delay(...) → 브로커(Redis/RabbitMQ) → 워커
상태 추적
  └─ Job 테이블 (jobs/model.py: JobStatus, JobType) + JobService.execute_with_status
```

관련 파일:

| 파일 | 역할 |
|---|---|
| `src/backend/base/langflow/core/celery_app.py` | Celery 앱 생성, 큐 라우팅 설정 |
| `src/backend/base/langflow/core/celeryconfig.py` | 브로커 설정 (`LANGFLOW_REDIS_HOST/PORT` → Redis, 없으면 RabbitMQ) |
| `src/backend/base/langflow/worker.py` | Celery 태스크 정의부 (현재 사실상 미사용) |
| `src/backend/base/langflow/services/task/service.py` | Celery/로컬 백엔드 추상화 (`TaskService`) |
| `src/backend/base/langflow/services/task/backends/celery.py` | `CeleryBackend` — `task_func.delay()` 요구 |
| `src/backend/base/langflow/services/database/models/jobs/model.py` | `Job` 테이블, `JobStatus` / `JobType` |
| `src/backend/base/langflow/api/v1/knowledge_bases.py:1085-1118` | 참고 패턴: Job 생성 + fire_and_forget |

### 1.2 현황 진단: "골격은 있으나 죽은 코드" (2026-07-07 코드 검증 완료)

Langflow에 Celery 실행 경로가 "없다"기보다, **한 번도 완성된 적 없는 골격**이 남아 있다.
아래 네 가지를 실제 코드에서 확인했다:

1. **기본 비활성.** `TaskService`가 `settings.celery_enabled`로 분기하며(`task/service.py:25`)
   기본값은 false → 모든 백그라운드 작업은 `AnyIOBackend`, 즉 **같은 프로세스의 asyncio 태스크**로 실행된다.
   현재 Langflow의 플로우 실행은 100% 인프로세스다.
2. **켜도 깨진다.** `CeleryBackend.launch_task`는 `.delay` 메서드를 가진 등록된 Celery 태스크만 받는다
   (`backends/celery.py:24-26`, 없으면 `ValueError`). 그런데 기존 호출부(KB 인제스천 등)는 일반
   async 함수를 넘기므로 `celery_enabled=true`로 켜는 순간 오류가 난다.
   → Celery로 돌릴 함수는 반드시 `@celery_app.task`로 등록된 별도 태스크여야 한다.
3. **worker.py 태스크는 아무도 안 쓴다.** API의 vertex 빌드 경로(`api/build.py:464`,
   `api/v1/chat.py:468`)는 그래프 객체의 메서드 `graph.build_vertex()`를 **직접 await**한다.
   `worker.py`의 Celery 태스크 `build_vertex`와는 이름만 같은 별개이며, 도달 경로가 없다.
4. **라우팅 패턴 불일치.** `celery_app.py:7`의 라우트 패턴은 `langflow.worker.tasks.*`인데
   실제 태스크 모듈은 `langflow.worker`라서 이름이 `langflow.worker.build_vertex`가 된다.
   패턴이 매칭되지 않아 기본 `celery` 큐로 간다. 신규 태스크 추가 시 라우팅 정리가 선행돼야 한다.
5. **워커 프로세스 서비스 초기화 부재.** 기존 태스크는 워커에서 DB/storage 등 서비스 스택을
   초기화하지 않는다(미완성). 신규 태스크는 부트스트랩을 직접 처리해야 한다.

## 2. 큐 배치 위치 결정 (2026-07-07 추가)

큐를 놓을 수 있는 자리는 3곳이고, 각각 성립 조건이 다르다.

| 자리 | 판정 | 이유 |
|---|---|---|
| ① 컴포넌트 내부 | ✗ 불가 | 아래 상술 — 데이터플로우 실행 모델과 충돌 |
| ② Langflow 플로우/Job 레벨 | △ 이론상 정답, 큰 공사 | §1.2의 죽은 골격을 살리는 작업 전체가 선행 조건 (B안) |
| ③ 파서 서비스(hwpparser) 내부 | ✓ 권장 | 병목의 근원(soffice 단일 인스턴스)에 큐를 둠. Langflow 무수정 (A안) |

**①이 불가능한 이유.** 컴포넌트는 output을 반환해야 다운스트림 노드가 이어받는
데이터플로우의 한 칸이다. 컴포넌트가 자기 작업을 큐에 넣으면:

```
enqueue 후 결과를 기다림 → 큐잉의 이득(즉시 반환·자원 해방) 소멸, 지연만 추가
enqueue 후 즉시 반환     → 다운스트림에 줄 output이 없음 — 플로우가 끊김
```

유일하게 말이 되는 변형은 "큐가 외부 서비스 안에 있고 컴포넌트는 제출+폴링하는 클라이언트"인데,
그것이 곧 ③(A안)이다. Langflow 자체 사례로도 확인된다: docling-serve 연동 컴포넌트
(`docling_remote.py`)가 정확히 이 구조다 — 비동기 태스크 API에 제출하고 `_poll_and_fetch_result`
(`docling_remote.py:208-254`)로 폴링한다.

**결정 기준은 "소비자가 누구냐"다:**

```
캔버스에서 노드로 문서 1~2건 변환        → A안만으로 충분
API로 수백 건 대량 인덱싱 (RAG 사전작업)  → B안 (Langflow Job 큐) + 그 워커가 파서 호출
둘 다                                   → A+B 조합 — 층이 달라 배타적이지 않음
```

## 3. A안: 파서 서비스(hwpparser) 쪽 큐 — 1단계 권장안

병목의 실체는 hwpparser 컨테이너 안의 **soffice 단일 인스턴스**(LibreOffice 데몬,
스레드 안전하지 않음)다. 큐와 워커를 파서 쪽에 두면 Langflow 코어는 한 줄도 수정하지 않는다.

### 3.1 손볼 곳

| 대상 | 변경 |
|---|---|
| `hwpparser/src/app.py` | 동기 엔드포인트를 비동기 태스크 API로 분리: `POST /convert/async` → `task_id` 즉시 반환(202) / `GET /status/{task_id}` / `GET /result/{task_id}`. 소용량 파일용 동기 엔드포인트는 하위 호환으로 유지 |
| hwpparser 신규 모듈 | 자체 celery app + 태스크. **워커 컨테이너 1개 = soffice 1개**이므로 워커당 `--concurrency=1`, 처리량은 워커 레플리카 수로 확장 |
| `hwpparser/docker-compose.yml` | redis(브로커) + worker 서비스 추가, `deploy.replicas`로 워커 수 조절. API 컨테이너는 접수/조회만 담당 |
| 번들 `sapieparser_remote.py` | 단발 POST → **제출+폴링** 루프로 변경. 참조 구현: `docling_remote.py:208-254` (500 재시도 상한 `MAX_500_RETRIES` 패턴까지 포함) |

### 3.2 처리 흐름

```
[Langflow 컴포넌트]                [hwpparser API]        [redis]      [worker(s)]
POST /convert/async (파일) ──▶ 저장 + task 발행 ──▶ 큐 ──▶ soffice 변환
        ◀── 202 {task_id} ──┘                                   │
GET /status/{id} (폴링) ──▶ 상태 조회 ◀──────────── 진행/완료 갱신
GET /result/{id} ────────▶ 결과 반환 (HTML/MD 텍스트 또는 PDF 바이트)
```

### 3.3 유의점

- 파일 전달: 업로드 바이트를 브로커에 태우지 말고 API 컨테이너가 공유 볼륨/스토리지에 저장한 뒤
  경로(또는 id)만 태스크 인자로 전달 (JSON 직렬화 원칙, §4.1과 동일).
- 결과 보관: result backend(redis) TTL 설정. PDF 같은 바이너리는 파일로 저장하고 경로만 반환.
- 컴포넌트 timeout: 폴링 총 대기 시간이 컴포넌트의 `timeout` input과 일치하도록.

## 4. B안: Langflow 쪽 Job 큐 — 대량 인제스천 단계에서 적용

트리거가 캔버스 노드가 아니라 **Langflow API(대량 인덱싱, KB 인제스천)** 일 때의 설계.
B안의 워커 태스크는 내부에서 httpx로 hwpparser(A안의 API)를 호출한다 — 즉 A안과 조합된다.

### 4.1 태스크 정의

`langflow/worker.py`(또는 라우팅 패턴에 맞춘 `langflow/worker/tasks.py`)에 전용 태스크 등록:

```python
@celery_app.task(bind=True, acks_late=True, soft_time_limit=300, max_retries=3)
def parse_document_task(self, job_id: str, file_id: str, options: dict) -> dict:
    ...
```

원칙:

- 인자는 **JSON 직렬화 가능한 값만** 전달 (job_id, file_id, 옵션 dict).
- `UploadFile`, ORM 객체, 파일 바이트를 직접 넘기지 않고 워커에서 storage service로 재조회.
- 라이브 객체(`ComponentWithCache`의 공유 캐시 등 프로세스 로컬 상태)에 의존하는 로직은 태스크 안으로 가져오지 않음.
- `celeryconfig.py`의 `accept_content`에서 pickle을 제거하고 json만 허용 (보안/호환성).

### 4.2 전용 큐 분리

파싱은 CPU/IO가 무거우므로 `parser` 전용 큐로 라우팅하고 워커를 분리 기동:

```python
celery_app.conf.task_routes = {
    "langflow.worker.parse_document_task": {"queue": "parser"},
}
```

```bash
uv run celery -A langflow.core.celery_app.celery_app worker -Q parser --concurrency=4
```

→ 이후 플로우 실행을 Celery로 옮기더라도 파싱 워커와 독립적으로 스케일 가능.

### 4.3 상태 추적: Job 테이블 재사용

KB 인제스천 패턴(`knowledge_bases.py:1085-1118`)을 따름:

1. API 핸들러: 파일을 storage에 저장 → `Job` 행 생성 → 태스크 발행 → `TaskResponse(id=job_id)` 즉시 반환
2. `JobType`에 `PARSING` 값 추가 (enum 확장, DB enum 마이그레이션 필요 여부 확인)
3. 태스크 본문: 시작 시 `RUNNING`, 완료/실패 시 `COMPLETED`/`FAILED`로 Job 갱신
4. 결과물은 storage 또는 DB에 저장 (Celery result backend에만 의존하지 않음)
5. 클라이언트는 기존 `/task/{job_id}` 폴링 경로로 조회

### 4.4 OSS 기본 환경 호환 (로컬 폴백)

Langflow 기본값은 브로커 없는 `celery_enabled=false`이므로 이중 경로 유지:

```python
if task_service.use_celery:
    parse_document_task.delay(job_id=..., file_id=..., options=...)
else:
    await task_service.fire_and_forget_task(
        job_service.execute_with_status,
        run_coro_func=perform_parsing,
        ...
    )
```

파싱 핵심 로직은 순수 코루틴(`perform_parsing`)으로 작성하고,
Celery 태스크는 이를 감싸는 얇은 래퍼로 유지 → 두 경로가 같은 코드를 실행.
`perform_parsing` 내부는 httpx로 hwpparser API(A안)를 호출한다.

### 4.5 워커 서비스 부트스트랩

태스크에서 DB 세션·storage service를 사용하려면 워커 프로세스에서 서비스 초기화 필요:

- Celery `worker_process_init` 시그널에서 `initialize_services` 호출, 또는
- 태스크 시작부에서 lazy 초기화

**확인 필요**: 기존 코드에 완성된 예가 없으므로(§1.2-5) 구현 시 async 서비스 초기화와
Celery의 sync 실행 모델(`async_to_sync`) 간 상호작용 검증 필요.

## 5. 구현 단계 (단계별 — A안 먼저)

### Phase 1: A안 (파서 큐화) — Langflow 무수정

| 단계 | 작업 | 산출물 |
|---|---|---|
| 1-1 | hwpparser에 celery app + 변환 태스크 | hwpparser 신규 모듈 |
| 1-2 | app.py 비동기 태스크 API 추가 (submit/status/result) | `hwpparser/src/app.py` |
| 1-3 | compose에 redis + worker(replicas) 추가 | `hwpparser/docker-compose.yml` |
| 1-4 | 번들 컴포넌트 폴링화 (docling_remote 패턴) | `src/bundles/sapieparser/.../sapieparser_remote.py` |
| 1-5 | E2E: 동시 요청 N건에서 큐 적체→순차 처리 확인 | 테스트 스크립트 |

### Phase 2: B안 (Langflow Job 큐) — 대량 인제스천 요구 발생 시

| 단계 | 작업 | 산출물 |
|---|---|---|
| 2-1 | 라우팅 정리 + `parser` 큐 추가 | `core/celery_app.py` 수정 |
| 2-2 | `JobType.PARSING` 추가 | `jobs/model.py` + 마이그레이션(필요 시) |
| 2-3 | 파싱 코루틴 `perform_parsing` 구현 (내부는 A안 API 호출) | 서비스 레이어 신규 모듈 |
| 2-4 | Celery 태스크 래퍼 + 워커 부트스트랩 | `worker.py` |
| 2-5 | API 엔드포인트 (Job 생성 + 이중 경로 발행) | `api/v1/` 또는 `api/v2/` 라우트 |
| 2-6 | 테스트 (로컬 경로 단위 + Celery 경로 통합) | `src/backend/tests/unit/` |

## 6. 운영 고려사항

- **브로커**: (B안) `LANGFLOW_REDIS_HOST`/`LANGFLOW_REDIS_PORT` 설정 시 Redis, 미설정 시 RabbitMQ(`BROKER_URL`).
  (A안) hwpparser compose에 전용 redis — Langflow 설정과 무관.
- **soffice 워커 특성**: soffice는 단일 인스턴스·스레드 비안전 → **워커당 concurrency=1 고정**,
  스케일은 워커 레플리카 수로. soffice 행업 대비 워커 헬스체크 + `soft_time_limit` 필수.
- **재시도**: `acks_late=True` + `max_retries`로 워커 크래시 시 재처리. 파싱 로직은 멱등하게 작성.
- **타임아웃**: `soft_time_limit`으로 대용량 문서 파싱의 무한 대기 방지. 초과 시 Job을 `TIMED_OUT`으로 갱신.
- **모니터링**: Celery flower 또는 Job 테이블 기반 조회 API로 큐 적체 관찰.

## 7. 미결정 사항 (구현 전 확정 필요)

- [ ] Phase 1에서 동기 엔드포인트(`/hwp2html/clean` 등)를 유지할지, 파일 크기 기준으로 자동 분기할지
- [ ] parser의 구체적 입력 소스 (업로드 파일 / KB 문서 / 플로우 컴포넌트 연동)
- [ ] 파싱 결과물 저장 위치 및 스키마 (storage 파일 vs DB 테이블 / A안은 result TTL)
- [ ] (B안) API 버전 (v1 vs v2) 및 엔드포인트 경로
- [ ] (B안) `JobType` enum 확장 시 기존 DB enum 타입 마이그레이션 필요 여부

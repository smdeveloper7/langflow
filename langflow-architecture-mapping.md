# Langflow 아키텍처 — 개념 흐름도와 실제 코드 경로 매핑

> 기준: `docs/agents/ARCHITECTURE.md` + 저장소 실물 확인 (2026-07 기준, main 브랜치)

## 1. 개념 흐름도 (문서상의 계층)

```
frontend (TS)  ──HTTP──▶  langflow (배포판: 통합 묶음)
                              │
                              ▼ import 가능
                          langflow-base (플랫폼: api, 서비스, 그래프, DB, alembic)
                              │
                              ▼ import 가능
                          lfx (런타임: 실행기 코어, 기본 프리미티브, 컴포넌트)
                              │
                              ▼ import 가능
                          langchain-core, pydantic, 서드파티 SDK
```

- 의존성은 **위 → 아래 단방향**만 허용. 역방향(`lfx`에서 `langflow.*` import)은 경계 위반.
- 한 줄 요약: **`lfx`는 런타임, `langflow-base`는 플랫폼, `langflow`는 배포판.**
- ⚠️ 원문 다이어그램은 `langflow` 옆에 "api routers"라고 적어놨지만, **실제 api 라우터 코드는 langflow-base에 있다** (아래 3절 참고). 같은 문서의 결정 트리(코드 배치 규칙)가 맞고 다이어그램 라벨이 낡은 것.

## 2. 계층 ↔ 실제 디렉토리 매핑 (검증 완료)

| 계층 | 배포 패키지명 (pip) | 패키지 정의 | 실제 코드 위치 | import 이름 |
|---|---|---|---|---|
| frontend | (npm) | `src/frontend/package.json` | `src/frontend/src/` | — |
| langflow | `langflow` | **루트** `pyproject.toml` | `src/backend/langflow/` (`version/` 뿐) | `langflow.version` |
| langflow의 "통합" 부분 | `lfx-duckduckgo` 등 | `src/bundles/*/pyproject.toml` | `src/bundles/{arxiv,docling,duckduckgo,ibm}/` | 각 번들별 |
| langflow-base | `langflow-base` | `src/backend/base/pyproject.toml` | `src/backend/base/langflow/` | **`langflow`** |
| lfx | `lfx` | `src/lfx/pyproject.toml` | `src/lfx/src/lfx/` | `lfx` |
| 서드파티 | langchain-core 등 | 각 pyproject의 dependencies | `.venv/` | 각자 |

### 각 계층에 실제로 뭐가 들어있나

**`langflow` (배포판) — 사실상 메타 패키지**
- 자체 코드는 `src/backend/langflow/version/` 하나뿐.
- 실체는 루트 `pyproject.toml`의 의존성 목록: `langflow-base[complete]` + 벤더 번들들(`lfx-duckduckgo`, `lfx-arxiv`, `lfx-ibm`, …).
- 역할: "전부 한 방에 설치되는 완전판"을 파는 것. `pip install langflow` = base + 모든 통합.

**`langflow-base` (플랫폼) — 서버의 본체**
- 위치: `src/backend/base/langflow/`
- `api/` — FastAPI 라우터 (v1: 안정 표면 ~25개 / v2: 재설계 표면 4개 도메인)
- `services/` — 서비스 레이어 (auth, database, cache, storage, tracing, …)
- `alembic/` — DB 마이그레이션
- `initial_setup/starter_projects/` — 스타터 플로우 JSON (플로우 스키마의 정본 예시)
- `main.py` — FastAPI 앱 생성. **서버를 띄우는 코드가 여기** (langflow 패키지가 아님)

**`lfx` (런타임) — 실행 엔진 + 컴포넌트**
- 위치: `src/lfx/src/lfx/`
- `components/` — 내장 컴포넌트 전부 (벤더 통합 포함)
- `graph/` — 그래프 실행 엔진
- `base/` — 공유 프리미티브 (신규 공유 코드는 여기; `langflow/base/`는 레거시)
- `cli/` — `lfx run` / `lfx serve` (UI·DB 없이 플로우만 실행하는 경량 CLI)
- `custom/` — Component 기본 클래스 프레임워크

## 3. 헷갈리기 쉬운 지점 4가지

### ① 배포 패키지명 ≠ import 이름
`langflow-base`를 설치하면 `import langflow`가 된다. 코드 폴더 이름이 `langflow`이기 때문
(`src/backend/base/langflow/`). 그래서 `from langflow.api import ...`는
**langflow-base 패키지의 코드**를 import하는 것이다.

### ② `langflow` 패키지에는 api 코드가 없다
ARCHITECTURE.md 다이어그램의 "langflow (api routers)" 라벨은 낡은 표현.
api 라우터의 실물은 `src/backend/base/langflow/api/`(= langflow-base).
frontend가 HTTP로 대화하는 상대는 "실행 중인 langflow 앱 전체"이므로 화살표 자체는 맞다.

### ③ 컴포넌트 위치는 이동했다
옛 문서(AGENTS.md 구조도)에는 `src/backend/base/langflow/components/`라고 나오지만
이 디렉토리는 더 이상 존재하지 않는다. 현재 위치:
- 내장 컴포넌트: `src/lfx/src/lfx/components/`
- 별도 배포 번들: `src/bundles/`

### ④ `.venv/` 안의 코드를 읽지/고치지 말 것
IDE에서 `​.venv/lib/python3.12/site-packages/lfx/...` 파일이 열리는 경우가 있는데,
이는 설치된 사본이다. 소스는 항상 `src/lfx/src/lfx/...` 쪽을 봐야 한다.
(uv 워크스페이스: 루트 pyproject의 `[tool.uv.sources]`에 `workspace = true`로 선언되어
있어서, 개발 중에는 PyPI 버전 대신 저장소 안의 소스가 링크된다.)

## 4. 요청 하나가 흐르는 경로 (계층을 관통하는 예시)

플로우 실행 버튼을 눌렀을 때:

```
[frontend]      src/frontend/src/...
    │  POST /api/v1/build/{flow_id}  (HTTP)
    ▼
[langflow-base] src/backend/base/langflow/api/v1/chat.py  ← 라우터가 요청 수신
    │           src/backend/base/langflow/services/...    ← 인증, DB에서 플로우 로드
    ▼
[lfx]           src/lfx/src/lfx/graph/...                 ← 플로우 JSON → Graph 변환, 위상 순서 실행
    │           src/lfx/src/lfx/components/...            ← 각 노드(Component) 실행
    ▼
[서드파티]       langchain-core, openai SDK 등             ← 실제 LLM 호출
```

## 5. 빌드/배포는 어떻게 되나

| 대상 | 명령 | 실체 |
|---|---|---|
| langflow-base 빌드 | `make build_langflow_base` | `cd src/backend/base && uv build` → wheel 생성 → PyPI |
| langflow 빌드 | `make build_langflow` | 루트에서 `uv build` |
| 개발 실행 | `make backend` / `make frontend` | 빌드 없이 워크스페이스 소스 직접 사용 (핫 리로드) |

## 6. 이 구조의 설계 의도 (왜 3개로 쪼갰나)

계층 경계 = **설치 옵션의 경계**. 의존성이 단방향이어야 아래 세 가지를 따로 팔 수 있다:

| 설치 | 얻는 것 | 용도 |
|---|---|---|
| `pip install lfx` | 실행 엔진 + CLI만 | 만든 플로우를 서버 없이 실행 (`lfx run`) |
| `pip install langflow-base` | 코어 서버 (UI 포함, 벤더 SDK 최소) | 가벼운 서버 배포 |
| `pip install langflow` | 전부 (모든 벤더 통합 포함) | 완전판 |

개념적으로는 **계층형 아키텍처(단방향 의존) + 의존성 역전 원칙(DIP)** 의 조합:
- 아래 계층(lfx)은 위 계층(langflow)의 존재를 모른다.
- lfx가 상위 기능(예: 권한 검사)이 필요하면 lfx 안에 **추상 클래스**만 정의하고
  (`lfx/services/authorization/base.py`의 `BaseAuthorizationService`),
  구현은 langflow-base가 시작 시점에 서비스 레지스트리로 주입한다.
- LangChain이 `langchain-core / langchain / langchain-community`로 나뉜 것과 같은 패턴.

# 아키텍처 경계 (Architecture Boundaries)

> 이 문서는 [ARCHITECTURE.md](./ARCHITECTURE.md)의 한국어 번역본입니다. 원문이 변경되면 이 문서도 함께 갱신해야 합니다.

Langflow는 세 개의 Python 패키지와 하나의 프론트엔드로 구성되며, 단방향 의존성으로 계층화되어 있습니다. "서사에서 벗어난(off-narrative)" 코드 대부분은 경계 위반입니다. 새 파일을 추가하기 전에 이 문서를 먼저 읽으십시오.

## 패키지 의존성 그래프 (단방향만 허용)

```
frontend (TS)  ──HTTP──▶  langflow (api 라우터, 통합, 배포)
                              │
                              ▼ import 가능
                          langflow-base (서비스, 그래프, DB, alembic)
                              │
                              ▼ import 가능
                          lfx (실행기 코어, 기본 프리미티브, 컴포넌트)
                              │
                              ▼ import 가능
                          langchain-core, pydantic, 서드파티 SDK
```

### 의존성 규칙

- **`lfx`는 `langflow.*` 또는 `langflow-base.*`를 절대 import해서는 안 됩니다.** lfx 코드에서 서비스(인증, DB, 플로우 조회)가 필요하면, `lfx` 내부에 인터페이스를 정의하고 구현체는 `langflow`에서 주입하십시오. 현재 저장소의 `src/lfx/src/lfx/components/...` 내부에는 약 13개의 상향 `from langflow.*` import(인증, DB, 헬퍼)가 존재하는데, 이는 **알려진 위반 사항**입니다. 더 추가하지 말고, 가능하면 고치는 쪽을 택하십시오.
- **`langflow-base`는 `lfx`를 import할 수 있습니다.** 단, `langflow.components.<vendor>`의 벤더 특화 컴포넌트 모듈을 import해서는 안 됩니다.
- **`frontend`는 오직 HTTP/WebSocket으로만 `langflow`와 통신합니다.** 파일시스템 상태를 공유하지 않습니다.

## "이 코드는 어디에 두어야 하나?" 결정 트리

위에서부터 순서대로 내려가며, 처음 일치하는 항목에서 멈추십시오.

1. 프레임워크에 독립적인 플로우 실행, 기본 컴포넌트 클래스, 또는 `Component` 프리미티브인가?
   → `src/lfx/src/lfx/` (공유 프리미티브는 `base/`, lfx에 기본 탑재되는 내장 컴포넌트는 `components/`).
2. FastAPI 라우트, 인증, DB 모델, alembic 마이그레이션, 또는 라이프사이클이 관리되는 싱글턴인가?
   → `src/backend/base/langflow/` (`api/`, `services/X/`, `alembic/versions/`).
3. 벤더 통합(OpenAI, Pinecone, Notion 등) — 서드파티 SDK를 감싸는 `Component` 하위 클래스인가?
   → `src/lfx/src/lfx/components/<category>/`에 두고, 해당 `__init__.py`를 알파벳 순서로 갱신하십시오. 클래스 이름은 절대 변경하지 마십시오.
4. UI, 상태(state), 아이콘인가?
   → `src/frontend/src/`. 새 API 필드를 사용한다면 `src/frontend/src/types/`도 함께 갱신하십시오.
5. `lfx run` / `lfx serve`의 CLI 동작인가?
   → `src/lfx/src/lfx/cli/`.
6. SQLAlchemy/SQLModel 모델 변경인가?
   → `services/database/models/`에 두고, 반드시 `make alembic-revision message="..."`로 마이그레이션을 생성한 뒤 `make alembic-upgrade`로 적용하십시오.
7. 플로우 JSON 스키마 변경인가?
   → **중단하십시오.** 기존에 저장된 플로우는 계속 로드 가능해야 합니다. 버전 매핑을 추가하고, 기존 형태(shape)를 변형하지 마십시오. [CONTRACTS.md](./CONTRACTS.md)를 참고하십시오.
8. `lfx`와 `langflow-base` 양쪽에서 공유되는가?
   → `src/lfx/src/lfx/base/`에 두십시오. `langflow/base/`는 절대 안 됩니다.

## 의존성 방향 — 나쁜/좋은 예시

- **나쁨:** `src/lfx/...` 내부에서 `from langflow.services.deps import session_scope`.
  **좋음:** `lfx.interfaces.SessionProvider`를 정의하고 생성자 인자로 받으며, `langflow`가 시작 시점에 구체 구현인 `session_scope`를 연결(wiring)합니다.
- **나쁨:** `langflow-base` 코어(`api/`, `services/`, `graph/`) 내부에서 `from langflow.components.openai import ...`.
  **좋음:** 컴포넌트는 컴포넌트 레지스트리를 통해 동적으로 로드되며, 코어 코드는 `Component`만 참조합니다.
- **나쁨:** 단순 함수 모음에 불과한 새로운 `MyHelperService`.
  **좋음:** 유틸리티 함수는 `langflow/helpers/` 또는 `lfx/utils/`에 둡니다. 서비스는 `services/base.Service`를 상속하고 `services/factory.py`를 통해 등록됩니다.

## API 변경 프로토콜

- **`api/v1/`** 은 현재 운영 중인 안정(stable) 표면입니다(라우터 약 25개). 기존 v1 엔드포인트는 반드시 하위 호환을 유지해야 합니다: 필드 추가만 허용되며, 이름 변경이나 삭제는 금지입니다.
- **`api/v2/`** 는 **활발히 재설계 중인 표면**(`files`, `mcp`, `registration`, `workflow`)입니다 — 두 버전 모두 `api/router.py`에서 런타임에 마운트됩니다. v2는 "미래용"이 **아닙니다**; 예전 cursor 규칙은 틀린 내용이었습니다.
- 새 엔드포인트를 v2에 추가하는 경우는 (a) 호환성이 깨지는 형태 변경으로 v1 엔드포인트를 대체하거나, (b) 위 네 가지 v2 도메인에 속할 때뿐입니다. 그 외에는 v1에 추가(additive) 방식으로 확장하십시오.
- v1 엔드포인트에 대한 파괴적(breaking) 변경은 금지입니다. v2에 대응 엔드포인트를 추가하고 v1은 그대로 두십시오.

## 횡단(cross-cutting) 변경 프로토콜

요청/응답 형태(shape)를 건드리는 변경은 반드시 같은 PR에서 다음 세 곳을 함께 갱신해야 합니다:

1. `langflow/api/v{1,2}/schemas.py`(또는 해당 라우트의 로컬 스키마)의 pydantic 모델.
2. 영향받는 페이지/스토어가 사용하는 `src/frontend/src/types/`의 TypeScript 타입. OpenAPI 생성기가 없습니다 — 타입은 수작업으로 관리되므로, 이를 빠뜨리면 프론트엔드가 런타임에 소리 없이 깨집니다.
3. 필드가 영속화되는 경우: 새 alembic 리비전(`make alembic-revision message=...`) 생성, 그리고 그 형태가 저장된 플로우 내부에 존재한다면 플로우 JSON 버전 매핑도 추가.

세 가지를 한 PR에서 모두 할 수 없다면, 시작하지 마십시오.

## 서비스 vs 유틸리티 vs 컴포넌트

- **서비스** (`services/<name>/`): 라이프사이클이 관리되는 싱글턴으로, `services.base.Service`를 상속하고 `services/factory.py`를 통해 등록되며 `services/deps.py`로 접근합니다. 상태, 시작/종료 절차, 또는 공유 커넥션(DB, 캐시, 큐)이 있을 때 사용합니다.
- **유틸리티** (`helpers/`, `utils/`, 또는 `lfx/utils/`): 순수 함수 또는 순수에 가까운 함수. 공유 상태와 라이프사이클이 없을 때 사용합니다.
- **컴포넌트** (`src/lfx/src/lfx/components/<category>/`): 그래프에서 사용자에게 보이는 노드로, `Component`의 하위 클래스이며 `display_name`, `inputs`, `outputs`를 가집니다. 사용자가 캔버스에서 직접 연결해야 하는 경우에만 사용하십시오. 내부 배관(plumbing)을 노출하기 위해 컴포넌트를 추가하지 마십시오.

## `lfx/base/` vs `langflow/base/`

둘 다 존재하며, 둘 다 `agents/`, `data/`, `models/`, `prompts/`를 가지고 있습니다. 새로운 공유 프리미티브는 **`src/lfx/src/lfx/base/`** 에 추가하십시오. `langflow/base/` 트리는 레거시이므로 여기에 추가하면 안 됩니다.
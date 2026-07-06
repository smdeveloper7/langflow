# 사용자 대면 계약 (User-Facing Contracts)

> 이 문서는 [CONTRACTS.md](./CONTRACTS.md)의 한국어 번역본입니다. 원문이 변경되면 이 문서도 함께 갱신해야 합니다.

아래는 사용자가 의존하는 표면(surface)들입니다. 이를 소리 없이 깨뜨리는 것이 에이전트가 "이야기와 연결되지 않는" 작업을 배포하는 가장 흔한 방식입니다. 아래 항목을 변경하기 전에 반드시 이 문서를 읽으십시오.

## 계약 표면

| # | 계약 | 근거 위치 (source of truth) | 규칙 |
|---|------|------------------------------|------|
| 1 | 컴포넌트 클래스의 `name` 속성 | `class XComponent: name = "X"` | 절대 변경 금지. 저장된 플로우 JSON에서 노드를 매칭하는 데 사용됩니다. |
| 2 | 컴포넌트 클래스 식별자 (Python 클래스 이름) | `class XComponent` | 절대 변경 금지. `name`과 조합되어 해석(resolution)에 사용됩니다. |
| 3 | 컴포넌트 파일 경로 + 모듈 | `src/lfx/src/lfx/components/<cat>/<file>.py` | 이름 변경은 파괴적 변경입니다. 지원되는 절차는 새 컴포넌트를 기존 것 옆에 추가하고, 기존 클래스에 `legacy = True` + `replacement = ["<category>.<NewClassName>"]`를 설정하는 것입니다. 과거 `SUPPORTED_VERSIONS`(`src/backend/tests/constants.py`)에 대해 모든 컴포넌트 테스트의 `file_names_mapping`을 갱신하십시오. 스타터 프로젝트를 재생성하고 컴포넌트 인덱스를 재빌드하십시오. |
| 4 | 모든 컴포넌트의 input `name=` 과 `Output(name=...)` | 컴포넌트 파일 자체 | 이름 변경·제거 절대 금지. 저장된 플로우가 이를 키(key)로 참조합니다. 선택적(optional) input의 추가는 안전하지만, 제거나 이름 변경은 이를 사용한 모든 저장된 플로우를 깨뜨립니다. |
| 5 | Output 순서와 `Output.types` | 컴포넌트의 `outputs = [...]` 리스트 | 순서를 바꾸면 기존 플로우의 기본 선택이 바뀝니다. 타입을 좁히는 것은 파괴적 변경이고, 넓히는 것은 안전합니다. |
| 6 | input의 기본값 | input 스펙의 `default=` / `value=` | 기본값 변경은 그 기본값에 의존하던 사용자의 동작을 소리 없이 바꿉니다. 기존 기본값이 버그였던 경우가 아니라면 파괴적 변경으로 취급하십시오. |
| 7 | 플로우 JSON 스키마 | `src/backend/base/langflow/initial_setup/starter_projects/*.json` (정본 예시) | 최상위 `data.nodes[*].data.node` 형태와 `data.edges` 형태는 공개(public)입니다. 새 필드는 기본값이 있는 선택적 필드여야 합니다. |
| 8 | 공개 REST API | `docs/docs/API-Reference/api-flows-run.mdx`, `api-build.mdx`, `api-files.mdx`, `api-projects.mdx`, `api-logs.mdx`, `api-monitor.mdx`, `api-users.mdx`. `include_in_schema=False`인 엔드포인트는 내부용입니다. | 문서화된 엔드포인트는 안정(stable) 계약입니다. `POST /api/v1/run/{flow_id_or_name}`과 `POST /api/v1/webhook/{flow_id_or_name}`은 사용자 계약입니다 — 페이로드 형태와 상태 코드는 동결(frozen)되어 있습니다. |
| 9 | MCP 도구 노출 | `src/backend/base/langflow/api/v1/mcp.py`, `mcp_projects.py`. 도구 모드는 `Output.tool_mode` / `component_as_tool` 이름의 output으로 토글됩니다. | 기존 컴포넌트 output에서 `tool_mode=True`를 제거하거나 그 이름을 바꾸면, 이를 도구로 사용하는 모든 Agent 플로우가 깨집니다. |
| 10 | `Message` / `Data` / `DataFrame` 스키마 | `src/lfx/src/lfx/schema/message.py` (`text`, `sender`, `sender_name`, `session_id`, `flow_id`, `timestamp`, `properties`, `content_blocks`, `category`, `files`, `error`, `edit`, `duration`, `session_metadata`) | 컴포넌트 간 전송(wire) 포맷입니다. 필드는 기본값이 있는 경우에만 추가하십시오. 나열된 필드의 이름이나 타입을 바꾸면 실행 중인 모든 플로우가 깨집니다. |
| 11 | 환경변수 | `LANGFLOW_*`(서버)는 `src/backend/base/langflow/services/settings/base.py`와 `feature_flags.py`에 정의. `LFX_*`(실행기)는 `src/lfx/src/lfx/services/settings/base.py`에 정의하되, 일부는 `os.getenv`로 직접 읽음(예: `src/lfx/src/lfx/interface/components.py`의 `LFX_DEV`). | 공개 배포 계약입니다. 이름을 바꾸려면 두 이름을 모두 읽는 지원 중단(deprecation) 주기가 필요합니다. |
| 12 | 데이터베이스 스키마 | `src/backend/base/langflow/services/database/models/` + `alembic/versions/` | `make alembic-revision` 없이 모델을 수정하지 마십시오. 과거 마이그레이션은 절대 수정하지 마십시오. 커스텀 컴포넌트의 Python 소스는 사용자 DB에 저장됩니다 — `from langflow.X import Y`가 사용하는 import 경로를 리팩터링하면 그 행(row)들의 로딩이 깨집니다. |
| 13 | 스타터 프로젝트 JSON | `src/backend/base/langflow/initial_setup/starter_projects/*.json` | 각 파일은 실제 컴포넌트를 `name`/`type`으로 참조합니다. 컴포넌트 이름 변경, input 제거, output 타입 변경은 로딩을 깨뜨립니다. 컴포넌트를 변경했다면 반드시 영향받는 스타터 프로젝트를 다시 로드해 보십시오. |
| 14 | 웹훅 페이로드 형태 | `POST /api/v1/webhook/{flow_id_or_name}` | 외부 시스템이 여기에 POST합니다. 응답 상태(202 Accepted)와 `dict` 본문 형태는 동결되어 있습니다. |
| 15 | 컴포넌트 인덱스 | `src/lfx/src/lfx/_assets/component_index.json` | 프론트엔드가 소비하는 생성된(generated) 산출물입니다. 필드/output 추가 시 재생성이 필요하며, 라벨 추가 시 CI가 이를 강제합니다. |

## 변경 전 대조표 (Before-you-change matrix)

| 하려는 작업 | 확인 / 갱신할 것 |
|---|---|
| 컴포넌트 파일 이름 변경 | 새 파일을 옆에 추가; 기존 클래스에 `legacy = True` + `replacement = [...]` 설정; 모든 테스트의 `file_names_mapping` 갱신; 기존 타입에 대해 `starter_projects/*.json` grep |
| input `name=` 변경 | 하지 마십시오. 새 input을 옆에 추가하고 필요하다면 컴포넌트에 `legacy=True`로 기존 것을 지원 중단; 기존 이름에 대해 `starter_projects/*.json` grep |
| output 추가 또는 이름 변경 | 스타터 프로젝트 재생성; 컴포넌트 인덱스 재빌드 |
| 기본값 변경 | 파괴적 변경으로 취급. 스타터 프로젝트 + 테스트에서 의존 여부 grep |
| output에서 `tool_mode=True` 제거 | 이를 도구로 사용하는 에이전트 플로우/스타터 프로젝트 검색; 사용자에게 보이는 회귀(regression)입니다 |
| `Message` 필드 추가 | 반드시 기본값이 있는 `Optional`; 기존 필드 순서 변경 금지 |
| REST 엔드포인트 추가 | 사용자 대면이면 `docs/docs/API-Reference/`에 추가; 내부용이면 `include_in_schema=False` 설정 |
| DB 모델 수정 | `make alembic-revision message="..."`; 과거 리비전은 절대 수정 금지 |
| `LANGFLOW_*` / `LFX_*` 환경변수 변경 | 최소 한 개 마이너 버전 동안 기존 이름을 폴백으로 읽기; 릴리스 노트에 문서화 |
| 요청/응답 스키마 변경 | pydantic 스키마 + `src/frontend/src/types/` + (영속화되는 경우) alembic까지 하나의 PR에서 모두 갱신 |

## 무해해 보이지만 파괴적인 변경들

전부 정리(cleanup)처럼 보이지만, 사용자에게 보이는 회귀입니다.

- **컴포넌트의 `input_value` → `text` 이름 변경**: 그 input을 참조하는 저장된 플로우 100%가 연결(wiring)을 잃습니다.
- **`outputs = [a, b]`를 `[b, a]`로 재정렬**: 기본 선택을 쓰던 기존 플로우가 잘못된 output에서 라우팅됩니다.
- **`Output(types=["Message", "Data"])` → `["Message"]`로 좁히기**: `Data`로 해석되던 엣지가 로드 시 무효가 됩니다.
- **`default="gpt-4o-mini"`를 `default="gpt-5"`로 변경**: 사용자에게 소리 없이 다른 요금이 청구됩니다.
- **`langflow/components/foo/bar.py`를 `langflow/components/foo2/bar.py`로 이동**: 사용자 DB에 저장된 커스텀 컴포넌트 중 `from langflow.components.foo.bar import ...`를 쓰는 것들이 다음 로드에서 실패합니다. `file_names_mapping` 테스트는 나열된 과거 버전만 검증하고 사용자 코드는 검증하지 않으므로 통과해 버립니다.
- **벡터 스토어의 `as_dataframe`에서 `tool_mode=True` 제거**: 이를 도구로 호출하던 모든 Agent에서 그 도구가 사라집니다.
- **`Message`에 필수(required) 필드 추가**: 실행 중인 배포의 큐에 있는 모든 메시지가 다음 읽기에서 역직렬화에 실패합니다.
- **스타터 프로젝트 파일 이름 변경**: 문서와 튜토리얼의 딥링크가 404가 됩니다.

## 왜 중요한가

Langflow의 플로우는 프로덕션에서 실행되는 **영속화된 사용자 자산**입니다. 이를 로드하는 시스템은 의도적으로 관대하게 설계되어 있습니다: 새 필드를 허용하고, 없는 필드는 폴백하고, 로드 시 타입 마이그레이션을 적용합니다. 그 관대함의 대가가 위 표의 계약들입니다. 하나라도 깨면 시스템이 더 이상 우회할 수 없게 되고 — 플로우는 동작을 멈춥니다.

이 파일을 체크리스트로 취급하십시오. 변경이 표의 어느 행이라도 건드린다면 해당 규칙이 적용됩니다. 명시적인 지원 중단 계획 없이는 예외가 없습니다.

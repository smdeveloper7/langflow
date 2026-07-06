# 컴포넌트 개발 (Component Development)

> 이 문서는 [COMPONENTS.md](./COMPONENTS.md)의 한국어 번역본입니다. 원문이 변경되면 이 문서도 함께 갱신해야 합니다.

컴포넌트는 Langflow에서 작업의 단위입니다. 캔버스에서 노드로 렌더링되고, 플로우 JSON으로 영속화되며, Agent의 도구(tool)가 됩니다. 계약을 올바르게 잡으면 나머지 시스템이 따라오고, 잘못 잡으면 그 컴포넌트를 참조하던 모든 저장된 플로우가 고아가 됩니다.

컴포넌트는 **`src/lfx/src/lfx/components/<category>/`** 에 있습니다. `src/backend/base/langflow/components/` 아래의 미러 트리는 레거시 스텁입니다 — 거기에 파일을 추가하지 마십시오.

## 컴포넌트를 추가하기 전에 (결정 체크리스트)

순서대로 멈춰서 확인하십시오. 하나라도 답이 "예"라면 새 컴포넌트를 만들지 마십시오.

1. **이미 존재하는가?** 검색:
   ```bash
   rg -l 'display_name = ".*<keyword>.*"' src/lfx/src/lfx/components/
   ```
   그리고 카테고리 폴더를 확인하십시오. Calculator의 후회(두 개가 존재함, `tools/calculator.py`의 `legacy = True, replacement = ["helpers.CalculatorComponent"]` 참고)가 이 단계를 건너뛰면 벌어지는 일입니다.
2. **Agent가 `tool_mode=True`로 직접 호출할 수 있는 기존 도구/SDK의 얇은 래퍼인가?** 그렇다면 새로 만들지 말고 기존 컴포넌트의 해당 input에 `tool_mode=True`를 추가하십시오.
3. **범용 `tools/`나 `helpers/`가 아니라 벤더 번들**(예: `openai/`, `anthropic/`, `datastax/`)**에 속하는가?** 벤더 로직은 벤더 폴더에 둬야 번들이 독립적으로 배포·버전 관리될 수 있습니다.
4. **lfx 런타임 관심사**(그래프 실행, 스키마, IO 프리미티브)**인가, Langflow 앱 관심사**(인증, DB, 트레이싱)**인가?** 컴포넌트는 lfx입니다. 컴포넌트에서 `langflow.services.*`를 절대 import하지 마십시오.
5. **이 카테고리를 커버하는 기존 기본 클래스가 있는가?** 있으면 사용하십시오:
   - LLM → `LCModelComponent` (`openai/openai_chat_model.py` 참고)
   - 도구 → `LCToolComponent` (`tools/calculator.py` 참고)
   - 벡터 스토어 → `LCVectorStoreComponent` + `@check_cached_vector_store` (`vectorstores/local_db.py` 참고)
   - 채팅 IO → `ChatComponent` (`input_output/chat.py` 참고)

## 범위 규칙 (컴포넌트 하나, 일 하나)

- 컴포넌트 하나당 일 하나. description에 " and "(그리고)가 들어간다면 분리하십시오.
- **input 예산:** 눈에 보이는 input은 8개 이하를 목표로 하고, 나머지는 `advanced=True` 뒤로 밀어 넣으십시오. 모드 전환(Ingest/Retrieve 등)이 필요하면 `TabInput` + `update_build_config`로 무관한 필드를 숨기십시오 — `vectorstores/local_db.py` 참고.
- **output:** 기본은 주(primary) `Output(method=...)` 하나입니다. 다운스트림 노드가 정말로 다른 형태(Message vs DataFrame vs Data)를 필요로 할 때만 추가하십시오. 쓰지 않는 output을 추가하지 마십시오.
- Agent가 채울 수 있어야 하는 input에는 `tool_mode=True`를 표시하십시오(예: `local_db.py`) — 이것이 컴포넌트가 에이전트 도구가 되는 방식입니다.

## 파괴적 변경 목록 (한번 출시되면 잠김)

저장된 플로우는 컴포넌트를 문자열 식별자로 참조합니다. 컴포넌트가 머지되고 나면 다음은 **동결(frozen)** 됩니다 — 바꾸면 기존 사용자 플로우가 소리 없이 깨집니다:

- **클래스 이름** (이미 규칙에 있음).
- **`name = "..."` 클래스 속성**. **이것이 플로우 JSON의 식별자**이며, 클래스 이름이 아닙니다. `openai_chat_model.py`, `chat.py` 참고.
- 각 input의 **`name=...`**. `input_value` → `prompt`로 이름을 바꾸면 그것을 가리키던 모든 엣지가 고아가 됩니다.
- 각 output의 **`name=...`** 과 선언된 반환 타입. 다운스트림 노드는 둘 다로 매칭합니다.
- 기존 input의 **기본값**과 기본 동작 (기본값으로 저장된 플로우는 새 기본값으로 다시 로드됩니다).

컴포넌트를 제거하거나 재작업하려면 **제자리에서 수정하지 마십시오**. 올바른 카테고리 아래에 대체 컴포넌트를 추가한 뒤, 기존 것에 다음을 설정하십시오:

```python
legacy = True
replacement = ["<category>.<NewClassName>"]
```

(`tools/calculator.py`, `flow_controls/sub_flow.py` 참고). UI가 "Updates Available"을 표시하고 사용자를 마이그레이션합니다. 기존 클래스는 계속 import 가능한 상태로 남습니다.

이것이 보호하는 사용자 대면 표면 전체는 [CONTRACTS.md](./CONTRACTS.md)를 참고하십시오.

## 에이전트가 놓치는 관례들

코드베이스 전반에 나타나지만 옛 문서에는 거의 없는 것들입니다.

- **`name`** (클래스 속성): 플로우 JSON 식별자. 항상 명시적으로 설정하고 `__class__.__name__`에 의존하지 마십시오. 예: `chat.py`의 `name = "ChatInput"`.
- **`legacy = True` + `replacement = [...]`**: 지원 중단 짝. 항상 함께 씁니다. 예: `tools/calculator.py`.
- **input의 `tool_mode=True`**: 해당 input을 도구 인자로 하여 컴포넌트를 Agent 도구로 노출합니다. 예: `vectorstores/local_db.py`.
- **`real_time_refresh=True` + `update_build_config(self, build_config, value, name)`**: 동적 폼. 모드 전환과 종속 필드 숨김/표시에 사용합니다. 예: `openai/openai_chat_model.py`, `vectorstores/local_db.py`.
- **`metadata = {"keywords": [...]}`**: 컴포넌트 선택기의 추가 검색어. 예: `data_source/sql_executor.py`.
- **`minimized = True`**: 기본적으로 접힌 상태로 렌더링. 예: `input_output/chat.py`.
- **`documentation = "https://docs.langflow.org/..."`**: 노드 UI에서의 딥링크. 예: `input_output/chat.py`.

## 배치 규칙

- **벤더 특화 코드** → 벤더 폴더 (`openai/`, `anthropic/`, `datastax/`, `cohere/`, …). `tools/`도, `models/`도 아닙니다.
- **범용·벤더 무관 헬퍼** → `helpers/`, `processing/`, `logic/`, `flow_controls/`.
- **IO 프리미티브** → `input_output/`.
- 카테고리 `__init__.py`에 import를 **알파벳 순서**로 추가하십시오.
- **새 최상위 카테고리를 발명하지 마십시오.** 필요하다고 느껴진다면 그것은 팀과 먼저 논의하라는 신호입니다 — 카테고리는 UI 사이드바에 보이는 제품 표면의 일부입니다.

## 아이콘

모든 컴포넌트에는 아이콘이 필요합니다. 어울리는 것이 있으면 Lucide 아이콘을 쓰고, 커스텀 SVG는 벤더 로고에만 만드십시오.

### Lucide 아이콘 (기본)

```python
icon = "calculator"  # Lucide 아이콘 이름, 소문자
```

카탈로그는 https://lucide.dev/icons 참고.

### 커스텀 벤더 아이콘

브랜드 로고에는 프론트엔드 SVG 컴포넌트가 필요합니다. Python의 `icon` 문자열과 프론트엔드 매핑 키는 **정확히**(대소문자 구분) 일치해야 합니다.

1. **Python:** 컴포넌트에 `icon = "AstraDB"` 설정.
2. **프론트엔드 SVG 컴포넌트** — `src/frontend/src/icons/AstraDB/AstraDB.jsx`:
   ```jsx
   const AstraSVG = (props) => (
     <svg {...props}>
       <path fill={props.isDark ? "#ffffff" : "#0A0A0A"} d="..." />
     </svg>
   );
   ```
3. **래퍼** — `src/frontend/src/icons/AstraDB/index.tsx`:
   ```tsx
   import React, { forwardRef } from "react";
   import AstraSVG from "./AstraDB";

   export const AstraDBIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
     (props, ref) => <AstraSVG ref={ref} isDark={isDark} {...props} />
   );
   ```
4. **지연(lazy) import** — `src/frontend/src/icons/lazyIconImports.ts`:
   ```ts
   AstraDB: () =>
     import("@/icons/AstraDB").then((mod) => ({ default: mod.AstraDBIcon })),
   ```
5. UI에서 **라이트 모드와 다크 모드 둘 다** 확인.

### 아이콘 체크리스트

- [ ] Python `icon = "..."` 설정.
- [ ] 커스텀인 경우: `isDark` prop을 받는 SVG 컴포넌트, `forwardRef` 래퍼, `lazyIconImports.ts` 등록.
- [ ] 라이트/다크 모드 모두 확인.

## 컴포넌트 테스트

전체 테스트 계약은 [TESTING.md](./TESTING.md)를 참고하십시오. 빠른 참조:

- `ComponentTestBaseWithClient`(API 필요) 또는 `ComponentTestBaseWithoutClient`(순수 로직)를 상속.
- 세 개의 픽스처 제공: `component_class`, `default_kwargs`, `file_names_mapping`.
- 순수 로직의 LLM 경로에는 `MockLanguageModel` 사용; 실제 API 테스트에는 `@pytest.mark.api_key_required` 사용.
- 그래프 동작에는 Graph 테스트 패턴 사용: 빌드, `.set()`, `async_start`, 검증. 그래프 내부를 찌르지 마십시오.

## 정본(canonical) 예시들

막힐 때는 시작 전에 이 파일들을 읽으십시오:

- 동적 프로바이더 전환이 있는 LLM: `src/lfx/src/lfx/components/openai/openai_chat_model.py`
- `tool_mode`와 legacy/replacement가 있는 도구: `src/lfx/src/lfx/components/tools/calculator.py`
- 캐시 + 탭 input이 있는 벡터 스토어: `src/lfx/src/lfx/components/vectorstores/local_db.py`
- `minimized`가 있는 채팅 입력: `src/lfx/src/lfx/components/input_output/chat.py`
- 검색 가능한 메타데이터가 있는 컴포넌트: `src/lfx/src/lfx/components/data_source/sql_executor.py`
- Legacy + replacement 패턴: `src/lfx/src/lfx/components/flow_controls/sub_flow.py`

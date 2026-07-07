# 테스트 (Testing)

> 이 문서는 [TESTING.md](./TESTING.md)의 한국어 번역본입니다. 원문이 변경되면 이 문서도 함께 갱신해야 합니다.

백엔드 테스트의 관례입니다. 프론트엔드 테스트는 `src/frontend/`에 문서화된 표준 Jest/Playwright 패턴을 따릅니다.

## 프로젝트 정책: 모킹(mocking)을 피하라

실제 통합을 선호하십시오. "모킹한 테스트는 통과, 프로덕션은 실패" 패턴으로 여러 릴리스 주기를 낭비했습니다 — 관련 커밋 이력은 [ANTI-PATTERNS.md](./ANTI-PATTERNS.md)를 참고하십시오. 모킹은 다음 경우에만 사용합니다:

- 의존 대상이 LLM이고 테스트가 순수 로직을 검증할 때 → `tests/unit/mock_language_model.py`의 `MockLanguageModel` 사용.
- 의존 대상이 정말로 불안정하고 테스트 대상과 직교(orthogonal)할 때.

그 외에는: 실물을 호출하고, 자격 증명이 필요하면 `@pytest.mark.api_key_required` 마커를 붙이고, CI가 게이트하게 두십시오.

## 내장 픽스처

### `client` (FastAPI 테스트 클라이언트)

`src/backend/tests/conftest.py`에 정의. `ASGITransport` + `LifespanManager`를 통해 전체 앱에 연결된 비동기 `httpx.AsyncClient`입니다. 인메모리 SQLite와 모킹된 환경변수로 자동 구성됩니다. `@pytest.mark.noclient`로 건너뛸 수 있습니다.

```python
async def test_login_endpoint(client):
    response = await client.post("api/v1/login", data={"username": "foo", "password": "bar"})
    assert response.status_code == 200
```

인증이 필요한 라우트에는 `logged_in_headers` 픽스처를 함께 사용하십시오.

## 컴포넌트 테스트 기본 클래스

`src/backend/tests/base.py`에 위치.

| 기본 클래스 | `client` 생성? | 용도 |
|---|---|---|
| `ComponentTestBase` | 아니오 | 컴포넌트 버전 테스트의 핵심 로직 |
| `ComponentTestBaseWithClient` | 예 | `run()` 중 백엔드 서비스를 호출하는 컴포넌트 |
| `ComponentTestBaseWithoutClient` | 아니오 | 순수 로직 컴포넌트 |

### 필수 픽스처

모든 하위 클래스는 세 개의 픽스처를 제공합니다:

1. **`component_class`** — 테스트 대상 컴포넌트 클래스.
2. **`default_kwargs`** — 컴포넌트 인스턴스화에 쓸 kwargs dict (비어 있어도 됨).
3. **`file_names_mapping`** — 과거의 각 Langflow 버전(`src/backend/tests/constants.py::SUPPORTED_VERSIONS`)을 모듈/파일 이름에 매핑하는 `VersionComponentMapping` 목록. 컴포넌트가 추가되기 전의 버전에는 `DID_NOT_EXIST`를 사용.

```python
from tests.base import ComponentTestBaseWithClient, VersionComponentMapping, DID_NOT_EXIST
from langflow.components.my_namespace import MyComponent

class TestMyComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"foo": "bar"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            VersionComponentMapping(version="1.1.1", module="my_module", file_name="my_component.py"),
            VersionComponentMapping(version="1.0.19", module="my_module", file_name=DID_NOT_EXIST),
        ]
```

기본 클래스가 자동으로 제공하는 테스트:

- `test_latest_version` — 인스턴스화한 뒤 `run()`이 `None`을 반환하지 않는지 확인.
- `test_all_versions_have_a_file_name_defined` — `SUPPORTED_VERSIONS` 대비 매핑의 완전성 확인.
- `test_component_versions` (파라미터화) — 지원되는 각 버전에 대해 소스로부터 컴포넌트를 빌드하고 실행을 확인.

컴포넌트 파일의 이름을 바꾸거나 이동했다면, 지원되는 모든 버전에 대해 `file_names_mapping`을 **반드시** 갱신해야 합니다. 그러지 않으면 해당 버전들에 저장된 플로우가 로드에 실패합니다. [CONTRACTS.md](./CONTRACTS.md)의 3번 행을 참고하십시오.

## 그래프 테스트 패턴

그래프 엔진을 검증하는 테스트의 정본 패턴:

1. 연결된 컴포넌트들로 그래프를 빌드한다.
2. `.set()` 호출로 컴포넌트들을 연결한다.
3. `async_start`를 호출하고 결과를 순회한다.
4. 결과를 검증한다.

그래프 내부를 찌르지 마십시오. 테스트가 private 상태에 접근해야 한다면 테스트가 잘못됐거나 API가 잘못된 것입니다 — 잘못된 쪽을 고치십시오.

## 비동기 패턴

```python
@pytest.mark.asyncio
async def test_async_component():
    result = await component.async_method()
    assert result is not None
```

**잠들지(sleep) 말고 조건을 기다리십시오:** 경쟁 상태(race)를 가리려고 `time.sleep`이나 `asyncio.sleep`을 절대 쓰지 마십시오. 조건을 기다리십시오(`asyncio.wait_for`, 이벤트, 타임아웃이 있는 큐 읽기). sleep 기반 테스트는 구조적으로 불안정(flaky)합니다.

## Pytest 마커

- `@pytest.mark.api_key_required` — 외부 API 키가 필요. 키가 없으면 CI가 건너뜀.
- `@pytest.mark.no_blockbuster` — blockbuster 플러그인 건너뜀.
- `@pytest.mark.noclient` — `client` 픽스처 건너뜀.
- `@pytest.mark.asyncio` — 비동기 테스트 (일부 설정에서는 `pytest-asyncio` 자동 모드).

## 데이터베이스 테스트

`test_database.py`는 일괄(batch) 실행에서는 실패하고 단독 실행에서는 통과할 수 있습니다. DB 모델이나 마이그레이션을 건드렸다면 검증 과정에서 순차적으로 실행하십시오:

```bash
uv run pytest src/backend/tests/unit/test_database.py
```

과거 alembic 마이그레이션은 절대 수정하지 마십시오. 마이그레이션이 동작한다고 주장하기 전에 `make alembic-upgrade`를 끝까지 실행하십시오.

## API 엔드포인트 테스트

```python
async def test_flows_endpoint(client, logged_in_headers):
    flow_data = {"name": "Test", "data": {"nodes": [], "edges": []}}
    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert response.status_code == 201
```

이벤트 스트림 엔드포인트는 NDJSON 스트림을 소비하며 이벤트 순서를 검증하십시오:

```python
async for line in response.aiter_lines():
    if not line:
        continue
    parsed = json.loads(line)
    # 첫 이벤트는 vertices_sorted, 마지막은 end여야 한다.
```

## 스타터 JSON으로 플로우 테스트

`tests/unit/build_utils.py`의 헬퍼를 사용하십시오:

```python
from tests.unit.build_utils import create_flow, build_flow, get_build_events

flow_id = await create_flow(client, json_flow, logged_in_headers)
build_response = await build_flow(client, flow_id, logged_in_headers)
events_response = await get_build_events(client, job_id, logged_in_headers)
```

## 테스트 실행

```bash
make unit_tests                              # 모든 백엔드 유닛 테스트, 병렬
make unit_tests async=false                  # 순차 실행
uv run pytest path/to/test.py                # 파일 하나
uv run pytest path/to/test.py::test_name     # 테스트 하나

# lfx 테스트 — 반드시 src/lfx 안에서 `uv sync` 후 실행
cd src/lfx && uv sync && uv run pytest
```

## "테스트 통과"를 주장하기 전 검증 체크리스트

- [ ] 명령을 작성만 한 것이 아니라 실제로 실행했다.
- [ ] DB 코드를 건드렸다면 `test_database.py`를 순차 실행했다.
- [ ] 변경한 컴포넌트의 개별 테스트 파일을 실행했다.
- [ ] 연결된 이슈 없이 건너뛴(skip) 테스트가 없다.
- [ ] 잘못된 경계에 모킹을 추가하지 않았다.

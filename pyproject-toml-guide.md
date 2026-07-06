# TOML과 pyproject.toml 개념 정리

> Langflow 저장소의 실제 파일들을 예시로 사용. 추후 커스텀 컴포넌트 번들 제작 시 참고용.

## 1부. TOML 기본 문법

TOML(Tom's Obvious, Minimal Language)은 설정 파일 포맷이다. JSON보다 읽기 쉽고 YAML보다 모호함이 적어서 Python 패키징의 표준(`pyproject.toml`)으로 채택되었다.

### 키-값과 자료형

```toml
name = "langflow-base"            # 문자열
version = "0.8.0"
requires-python = ">=3.10,<3.14"

port = 7860                       # 정수
timeout = 1.5                     # 실수
legacy = true                     # 불리언 (소문자!)

keywords = ["nlp", "langchain"]   # 배열
maintainers = [                   # 여러 줄 배열 (마지막 쉼표 허용)
    { name = "Carlos", email = "carlos@langflow.org" },   # ← 인라인 테이블
]
```

### 테이블 `[section]` — 계층 구조 만들기

```toml
[project]                # 이후의 키들은 project 소속
name = "langflow-base"

[project.urls]           # 점(.)으로 중첩: project > urls
Repository = "https://github.com/langflow-ai/langflow"

[tool.uv.workspace]      # tool > uv > workspace 3단 중첩
members = ["src/backend/base", "."]
```

JSON으로 바꿔 생각하면 이해가 빠르다:

```json
{ "project": { "name": "langflow-base", "urls": { "Repository": "..." } } }
```

### 따옴표가 붙은 테이블 이름

키에 점(.)이나 특수문자가 들어가면 따옴표로 감싼다. 안 감싸면 점이 중첩으로 해석되기 때문:

```toml
[project.entry-points."langflow.extensions"]
#                     ^^^^^^^^^^^^^^^^^^^^^ "langflow.extensions"가 통째로 키 하나
lfx-duckduckgo = "lfx_duckduckgo"
```

### 배열 테이블 `[[section]]`

같은 이름의 테이블이 여러 개 반복될 때 (Langflow에서는 드물게 등장):

```toml
[[tool.mypy.overrides]]
module = "foo.*"

[[tool.mypy.overrides]]
module = "bar.*"
```

## 2부. pyproject.toml의 구조 — 자주 쓰는 개념

pyproject.toml은 **패키지 명세서 + 도구 설정 파일**을 겸한다. 크게 세 영역:

| 영역 | 누가 읽나 | 역할 |
|---|---|---|
| `[project]` | pip, uv (표준, PEP 621) | 패키지 신원·의존성 선언 |
| `[build-system]` | 빌드 도구 (표준, PEP 517) | wheel을 어떻게 만들지 |
| `[tool.*]` | 각 도구 (비표준, 자유 영역) | pytest, ruff, mypy, uv 등의 설정 |

### `[project]` — 패키지 신원

```toml
[project]
name = "langflow-base"        # PyPI 배포명 (pip install 할 때 쓰는 이름)
version = "0.8.0"
requires-python = ">=3.10,<3.14"
dependencies = [ ... ]        # 항상 설치되는 의존성
```

⚠️ **배포명 ≠ import명**. import 이름은 `[tool.hatch.build.targets.wheel]`의
`packages = ["langflow"]`가 결정한다 — wheel에 담기는 폴더 이름이 import 이름이 된다.
langflow-base를 설치하면 `import langflow`가 되는 이유.

### 버전 지정자 (dependencies 안의 기호들)

```toml
dependencies = [
    "fastapi>=0.115.2,<1.0.0",   # 범위: 0.115.2 이상, 1.0 미만
    "sqlmodel==0.0.22",          # 정확히 이 버전만 (충돌로 데인 흔적일 때가 많음)
    "lfx~=0.3.0",                # "호환 릴리스": >=0.3.0,<0.4.0 과 동일
    "langchain~=0.3.27",         # >=0.3.27,<0.4.0
]
```

| 기호 | 의미 |
|---|---|
| `==` | 정확히 그 버전 |
| `>=`, `<` | 범위 |
| `~=X.Y.Z` | `>=X.Y.Z` 이면서 `<X.(Y+1).0` — "패치 버전만 올려도 됨" |
| `!=` | 특정 버전 제외 |

### 환경 마커 — 조건부 설치

`;` 뒤에 조건을 붙이면 해당 환경에서만 설치된다:

```toml
"jq>=1.7.0,<2.0.0; sys_platform != 'win32'",            # Windows 제외
'elevenlabs==1.58.1; python_version == "3.12"',          # Python 3.12에서만
"mlx>=0.29.0; sys_platform == 'darwin' and platform_machine == 'arm64'",  # 애플 실리콘 맥만
```

### `[project.optional-dependencies]` — extras (선택 설치 메뉴판)

핵심 개념. **사용자가 대괄호로 골라 설치하는 부가 의존성**:

```toml
[project.optional-dependencies]
openai = ["langchain-openai>=0.3.0,<1.0.0", "openai>=1.68.2,<2.0.0"]
chroma = ["chromadb>=1.0.0,<2.0.0"]
```

```bash
pip install langflow-base                # 코어만
pip install langflow-base[openai]        # 코어 + OpenAI
pip install "langflow-base[openai,chroma]"   # 조합
```

**메타 extra 트릭** — 자기 자신의 extras를 참조해서 세트 메뉴를 만들 수 있다:

```toml
complete = [
    "langflow-base[openai]",
    "langflow-base[chroma]",
    # ... 전부 나열
]
all = ["langflow-base[complete]"]        # 별칭
```

langflow 패키지가 `"langflow-base[complete]"` 한 줄로 모든 통합을 끌어오는 원리.

### `[dependency-groups]` — 개발 전용 의존성 (PEP 735)

extras와 헷갈리기 쉬운데 용도가 다르다:

| | extras | dependency-groups |
|---|---|---|
| 대상 | **사용자** (배포됨) | **개발자** (배포 안 됨) |
| 설치 | `pip install pkg[이름]` | `uv sync --group dev` |
| 예 | `[openai]`, `[complete]` | pytest, mypy, ruff |

```toml
[dependency-groups]
dev = ["pytest>=8.2.0", "mypy>=1.11.0", "ruff>=0.12.7"]
```

Langflow에서 서브패키지 테스트 전에 `uv sync --group dev --package langflow-base`를
하라는 이유가 이것 — 기본 sync는 dev 그룹을 안 깔 수 있다.

### `[project.scripts]` — 터미널 명령어 만들기

```toml
[project.scripts]
langflow-base = "langflow.__main__:main"
#  ^명령어 이름      ^모듈 경로        ^함수
```

설치하면 `langflow-base`라는 셸 명령이 생기고, 실행하면 `langflow/__main__.py`의 `main()`이 호출된다.

### `[project.entry-points]` — 플러그인 등록 (번들 제작 시 핵심!)

scripts의 일반화 버전. "이 이름공간에 나를 등록해 달라"는 선언으로,
**호스트 앱이 설치된 플러그인을 자동 발견하는 표준 메커니즘**이다.

Langflow 확장 번들의 실물 (`src/bundles/duckduckgo/pyproject.toml`):

```toml
[project.entry-points."langflow.extensions"]
lfx-duckduckgo = "lfx_duckduckgo"
```

동작 방식: Langflow가 기동할 때 `langflow.extensions` 그룹에 등록된 패키지들을
`importlib.metadata`로 스캔 → 각 패키지 안의 `extension.json` 매니페스트를 찾아
컴포넌트를 로드한다. **pip install만 하면 컴포넌트가 자동으로 나타나는 원리.**

### `[build-system]` — 빌드 도구 선언

```toml
[build-system]
requires = ["hatchling"]              # 빌드에 필요한 패키지
build-backend = "hatchling.build"     # wheel을 만드는 주체
```

`uv build` 실행 시 이 선언을 읽어 hatchling으로 wheel/sdist를 만든다.
(hatchling 외에 setuptools, flit, maturin 등이 있고 hatchling이 요즘 대세.)

### `[tool.*]` — 각종 도구의 설정 (자유 영역)

패키징과 무관. 각 도구가 자기 섹션을 읽는다:

```toml
[tool.pytest.ini_options]      # pytest 설정
testpaths = ["tests"]

[tool.mypy]                    # 타입 체커 설정
plugins = ["pydantic.mypy"]

[tool.hatch.build.targets.wheel]   # hatchling 빌드 설정
packages = ["langflow"]        # ← wheel에 담을 폴더 = import 이름 결정

[tool.uv.workspace]            # uv 모노레포 설정
members = ["src/backend/base", ".", "src/lfx"]

[tool.uv.sources]              # "PyPI 말고 로컬 소스를 써라" 조달처 지정
langflow-base = { workspace = true }
```

### uv 워크스페이스 개념 정리

- `[tool.uv.workspace] members` — "이 저장소 안에 배포 패키지가 여러 개 있다"는 선언 (모노레포).
- `[tool.uv.sources]` — 멤버들이 서로를 의존할 때 **PyPI 배포판 대신 옆 폴더의 소스를
  연결**하는 배선. 이게 없으면 코드를 고쳐도 PyPI에서 받은 옛 버전이 실행된다.
- 개발 중에는 소스가 직접 링크(핫 반영)되고, 릴리스 때만 `uv build`로 wheel을 만든다.

## 3부. Langflow 번들 pyproject.toml 해부 (커스텀 컴포넌트 번들 예습)

`src/bundles/duckduckgo/pyproject.toml`이 최소 완결 예시다:

```toml
[project]
name = "lfx-duckduckgo"                  # 번들 관례: lfx-<이름>
version = "0.1.1"
dependencies = [
    "lfx>=1.10.0.dev0,<2.0.0",           # lfx에만 의존 (langflow 의존 금지!)
    "ddgs>=9.0.0",                       # 감싸는 벤더 SDK
]

[project.entry-points."langflow.extensions"]
lfx-duckduckgo = "lfx_duckduckgo"        # 자동 발견용 등록

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/lfx_duckduckgo"]
include = [
    "src/lfx_duckduckgo/extension.json",         # 매니페스트 (컴포넌트 목록·호환성)
    "src/lfx_duckduckgo/components/**/*.py",     # 컴포넌트 소스
]
```

번들 제작 시 챙길 것:

1. **의존성은 lfx까지만** — 계층 규칙상 번들 컴포넌트는 `langflow.*`를 import하면 안 된다.
2. **entry-point 등록** — `langflow.extensions` 그룹에 패키지 경로를 등록해야 발견된다.
3. **extension.json 매니페스트** — 컴포넌트 목록과 lfx 호환 버전(`"lfx": {"compat": [...]}`)을 선언.
4. **wheel에 매니페스트 포함** — `include`에 extension.json을 명시해야 설치본에서 로더가 찾는다.
5. 기존 번들 4개(`src/bundles/{arxiv,docling,duckduckgo,ibm}`)와 `src/bundles/PORTING.md`가 참고 자료.

## 4부. 빠른 참조 — "이 섹션은 뭐지?" 치트시트

| 섹션 | 한 줄 요약 |
|---|---|
| `[project]` | 패키지 이름·버전·의존성 (pip이 읽음) |
| `dependencies` | 항상 설치되는 필수 의존성 |
| `[project.optional-dependencies]` | extras — `pkg[이름]`으로 골라 설치하는 메뉴판 |
| `[dependency-groups]` | 개발 도구 (배포 안 됨, `uv sync --group`) |
| `[project.scripts]` | 터미널 명령어 ↔ Python 함수 연결 |
| `[project.entry-points."그룹"]` | 플러그인 자동 발견 등록부 |
| `[build-system]` | wheel 만드는 도구 지정 |
| `[tool.hatch.build.targets.wheel]` | wheel에 담을 폴더 (= import 이름 결정) |
| `[tool.uv.workspace]` | 모노레포 멤버 목록 |
| `[tool.uv.sources]` | "PyPI 말고 로컬 소스" 조달처 지정 |
| `[tool.pytest/mypy/ruff/...]` | 각 도구의 설정 (패키징 무관) |

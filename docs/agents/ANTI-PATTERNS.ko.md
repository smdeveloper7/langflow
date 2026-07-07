# 안티패턴과 흉터 조직 (Anti-Patterns and Scar Tissue)

> 이 문서는 [ANTI-PATTERNS.md](./ANTI-PATTERNS.md)의 한국어 번역본입니다. 원문이 변경되면 이 문서도 함께 갱신해야 합니다.

이것들은 전투의 흉터입니다. 여기의 모든 규칙은 실제로 반복된 실패 — 커밋, 되돌리기(revert), 또는 명시적인 프로젝트 교훈 — 를 인용합니다. 무언가를 "그냥" 바꾸려는 순간 이 파일을 읽으십시오. 아래의 하지 마라/하라 규칙 대부분은 프로덕션을 깨뜨린 한 줄짜리 "작은 수정"에서 시작됐습니다.

## 하지 마라 / 하라 (이유와 함께)

1. **스타터 프로젝트와 컴포넌트 인덱스를 재생성하지 않은 채 컴포넌트에 필드를 추가하거나 이름을 바꾸지 마십시오.**
   *이유:* 커밋 `1a9f4548c`, `5987421bd`, `bbe1dad7c`, `69d29a4c6`, `67af71450`, `4f9beebc0`은 전부 같은 "필드 추가하고 그냥 배포했다" 실수를 치우는 `fix:` 커밋입니다. CI(`9dad1965c`)가 이제 라벨 추가 시 인덱스를 동기화하지만 — 그것은 안전망이지 대체재가 아닙니다.

2. **컴포넌트 클래스 이름, display name, 모듈 경로를 바꾸지 마십시오.** 불가피하다면 새 컴포넌트를 기존 것 옆에 추가하고, 기존 클래스에 `legacy = True` + `replacement = ["<category>.<NewClassName>"]`를 설정하고, 지원되는 모든 버전의 `file_names_mapping`을 테스트에서 갱신하십시오.
   *이유:* 클래스 이름이 저장된 플로우의 키입니다. `setup.py`에는 클래스 이름 변경 매핑이 없습니다 — 거기의 `type_migrations` 맵은 output 타입 문자열(`Data` → `JSON`, `DataFrame` → `Table`)만 처리합니다. 뒷정리 소동은 `2a7c56e84`(`IngestionDescriberComponent` → `FileDescriptionGeneratorComponent`)와 `f5a0d52197`(스타터 프로젝트 이름 변경)을 보십시오. 전체 목록은 [CONTRACTS.md](./CONTRACTS.md)를 참고하십시오.

3. **프로덕션이 호출하는 경계와 다른 경계에서 모킹하지 마십시오.** 프로덕션이 `subprocess.Popen`을 쓴다면 `Popen`을 모킹하십시오 — `run`이 아니라.
   *이유:* `a747135d1`, `bc433c375` — 모킹된 테스트는 통과했고 프로덕션은 실패했습니다. **더 나은 방법: 아예 모킹하지 마십시오** — 프로젝트 정책은 "테스트에서 모킹을 피하라"입니다. 실제 통합을 쓰거나, 순수 로직의 LLM 경로에는 `MockLanguageModel`을 쓰십시오.

4. **그래프 내부를 찔러서 Graph 테스트를 작성하지 마십시오.**
   *이유:* 정본 패턴은 빌드 → `.set()`으로 연결 → `async_start` 호출 → 결과 순회 → 검증입니다. 이를 우회하는 테스트는 사용자가 쓰는 방식대로 그래프를 검증하지 않습니다.

5. **증상을 없애려고 재시도를 추가하거나, except를 넓히거나, 타입을 확장하지 마십시오.**
   *이유:* "변경이 무언가를 고쳤다는 증거가 없다면 그것은 수정이 아닙니다." 되돌리기 연쇄 `9cdbf1b23`, `35aad2f2e`, `e3b90b7351`을 보십시오 — 해결이 아니라 은폐였던 수정들이며, 결국 되돌려야 했습니다.

6. **추측으로 의존성 버전을 올리지 마십시오.** 충돌이 로컬에서 재현되는지, 그리고 새 버전이 실제로 그것을 해결하는지 확인하십시오.
   *이유:* `cf659f0d0`, `ef6a303406`, `38d142a72`, `9029c4b61` — 반복된 의존성 충돌 뒷정리.

7. **모델 ID, MCP 도구 이름, API 표면을 지어내지 마십시오.** 레지스트리, 배치 디스패처, `models.py`를 먼저 읽으십시오.
   *이유:* `9f1402ed9`(`가상의 gpt-5.3 id 제거`), `cecc4a6c2`(`배치 디스패치와 일치하도록 layout 도구를 layout_flow로 노출`).

8. **`uv` 명령이 있는데 날것의 `langflow run` / `python`을 쓰지 마십시오.** 항상 `uv run`. lfx 테스트는 특히: langflow가 딸려오지 않도록 `src/lfx` 안에서(`src/lfx/src/lfx`가 아님) `uv sync`.
   *이유:* lfx는 langflow가 설치되지 않은 상태로 테스트 가능해야 합니다. 섞어 쓰면 의존성 누수가 가려집니다.

9. **`make alembic-upgrade`를 끝까지 실행하지 않은 채 데이터베이스 마이그레이션을 추가하지 마십시오.** 그리고 `uv run pytest src/backend/tests/unit/test_database.py`를 순차 실행하십시오.
   *이유:* `d8b9cc38f`, `c30150a2d`, `6585fe661`. `test_database.py`는 일괄 실행에서 통과하고 단독 실행에서 실패할 수 있습니다 — 에이전트들이 이 테스트 실행을 빼먹곤 했습니다.

10. **경쟁 상태(race condition)를 재현한 통합 테스트 없이 고쳤다고 주장하지 마십시오.** Agent 이중 실행과 큐 누수는 계속 재발합니다.
    *이유:* `8a993ac90`, `42e84d0fd`, `749865b31`, `f30b291f8`.

11. **에이전트를 혼란시키는 output에 `tool_mode=True`를 추가하지 마십시오** (예: dataframe 표면).
    *이유:* `cbc54108`(`as_dataframe의 tool_mode=True 제거`), `35aad2f2e`(원래 비활성화의 되돌리기). output의 도구 노출은 사용자 계약입니다 — 켰다 껐다 하지 마십시오.

12. **PR의 범위를 넓히지 마십시오.** 밀접하게 관련된 후속 작업은 새로 쌓는 PR이 아니라 기존 열린 PR에 속합니다.

13. **로컬에서 테스트를 실행하지 않고 배포하지 마십시오.** 채팅에 테스트 명령을 타이핑하는 것은 실행이 아닙니다.

14. **자잘한 "wip" 커밋을 만들지 마십시오.** 모든 것이 완료되고 테스트된 뒤, 논리적 변경 하나당 하나의 일관된 커밋.

15. **사용자의 명시적 확인 없이 push하거나 PR을 열지 마십시오.** 이미 열린 PR에서 CI를 반복하는 중의 push는 괜찮습니다. 새 PR을 열거나 새 브랜치를 push하는 것은 안 됩니다.

## 수정처럼 보이지만 수정이 아닌 것들

- 불안정한 호출 주위에 `try/except Exception: pass` 추가.
- 조건을 기다리는(await) 대신 경쟁 상태를 피하려는 `time.sleep` 추가.
- "혹시 몰라서" 의존성 버전 올리기.
- 연결된 이슈 없이 실패하는 테스트에 `@pytest.mark.skip` 붙이기.
- 타입을 고치는 대신 `# type: ignore`로 바꾸기.
- 근본 원인을 찾는 대신 증상(UI 플래그, 도구 플래그) 되돌리기.
- 잘못된 출력에 맞춰 단언(assertion)을 바꿔서 테스트 "고치기".

## 완료를 주장하기 전에

- [ ] `make format_backend`와 `make lint`가 깨끗함.
- [ ] 변경된 표면의 테스트를 로컬에서 실행하고 통과함 — 타이핑만 한 것이 아니라.
- [ ] 컴포넌트 필드/output이 바뀌었다면: 스타터 프로젝트 재생성 및 `component_index.json` 재빌드.
- [ ] 클래스/모듈 이름이 바뀌었다면: 기존 클래스를 `legacy=True` + `replacement=[...]`로 유지; 지원되는 모든 버전의 `file_names_mapping` 갱신.
- [ ] 자잘한 "wip" 커밋 없음. 논리적 변경 하나당 하나의 일관된 커밋.
- [ ] "Generated with Claude Code" / `Co-Authored-By: Claude` 트레일러 없음.
- [ ] 명시적으로 허가받지 않은 `--no-verify` 없음.
- [ ] 사용자가 명시적으로 요청하기 전까지 push 및 PR 열기 금지.
- [ ] PR 설명에 테스트 계획 체크리스트 없음, Jira 링크/ID 없음.

## 맥락을 찾을 곳 — 지어내지 마십시오

- **스타터 프로젝트:** `src/backend/base/langflow/initial_setup/starter_projects/`. 필드/output 변경 시 반드시 재생성.
- **컴포넌트 인덱스:** `src/lfx/src/lfx/_assets/component_index.json` (`9dad1965c`에서 추가된 인덱스 동기화 워크플로우로 재빌드).
- **Output 타입 마이그레이션:** `src/backend/base/langflow/initial_setup/setup.py`의 `type_migrations` 맵 — *output 타입 문자열*의 이름 변경(예: `Data` → `JSON`)만 처리합니다. 컴포넌트 클래스 이름은 재매핑하지 않습니다. 클래스 이름 변경에는 `legacy=True` + `replacement=[...]`를 쓰십시오.
- **컴포넌트 테스트의 버전 매핑:** `src/backend/tests/constants.py::SUPPORTED_VERSIONS`와 각 테스트의 `file_names_mapping`.
- **릴리스 노트 / 체인지로그:** `docs/docs/Support/release-notes/` — 어떤 동작이 "새것"이라고 주장하기 전에 확인하십시오. 많은 기능이 현재 작업보다 먼저 존재합니다.
- **MCP 도구 카탈로그:** 배치 도구를 통해 디스패치됩니다 — 이름이 일치해야 합니다 (`cecc4a6c2`가 "도구 이름을 추측했다" 실패의 정본 사례).
- **모델 / 프로바이더:** 실제 모델 ID는 프로바이더의 목록 엔드포인트나 우리의 어댑터에서 옵니다. 학습 데이터의 기억에서 가져오지 마십시오 (`9f1402ed9`).
- **마이그레이션:** `src/backend/base/langflow/alembic/versions/` — 새로 추가하기 전에 항상 최근 두 개를 읽으십시오.

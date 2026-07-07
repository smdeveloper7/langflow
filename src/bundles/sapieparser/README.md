# lfx-sapieparser

HWP/HWPX 문서 파싱 컴포넌트를 담은 Langflow Extension Bundle.

| 컴포넌트 | 방식 | 기능 |
|---|---|---|
| **HWP Parser** | remote | 상위의 HwpParser 서비스(LibreOffice+H2Orestart)를 호출해 `.hwp`/`.hwpx` → HTML / Markdown / PDF 변환 |
| **HWPX Text Extractor** | inline | 외부 서비스 없이 `.hwpx`에서 문단 텍스트 추출 |

## 빌드

```bash
cd langflow-bundle
uv build          # dist/ 에 wheel 생성
```

## 설치

```bash
# 로컬 개발 (수정 즉시 반영)
uv pip install -e langflow-bundle/

# 배포 (폐쇄망 포함) — wheel 파일 하나면 됨
pip install lfx_sapieparser-0.1.0-py3-none-any.whl
```

Langflow 도커 배포에 포함하려면:

```dockerfile
FROM langflowai/langflow:latest
COPY dist/lfx_sapieparser-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/lfx_sapieparser-0.1.0-py3-none-any.whl
```

설치만 하면 Langflow가 `langflow.extensions` entry-point로 자동 발견하며,
사이드바에 **Sapie Parser** 번들로 나타난다 (`ext:sapieparser:*` ID).

## HWP Parser 컴포넌트의 api_url

| 배포 형태 | api_url |
|---|---|
| Langflow 호스트 실행 + 파서 도커 | `http://localhost:40000` |
| 둘 다 도커, 같은 네트워크 | `http://hwp_parser:8000` |

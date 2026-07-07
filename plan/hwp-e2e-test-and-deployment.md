# 계획: HwpParser 실서비스 E2E 테스트 + Langflow 배포 구성안

> 작성: 2026-07-06 · 상태: **완료** (Phase A 전 항목 통과 — 하단 결과 참조)
> 검토 결과: ① 네트워크 `docker network create`로 생성 ② 포트 40000 유지 ③ compose 예시는 본 문서 내 예시로 보관 ④ 테스트 문서는 data 폴더의 실제 hwp 아무거나 사용
> 대상: `HWPParserRemote` 컴포넌트 (src/lfx/src/lfx/components/data_source/hwp_parser_remote.py)

## 목표

1. hwpparser 컨테이너를 실제로 띄워 `HWPParserRemote` 컴포넌트의 종단(E2E) 동작을 검증한다 — 모의 서버가 아닌 실물 LibreOffice+H2Orestart 변환 결과 확인.
2. Langflow 배포 관점에서 이 파서 서비스를 어떻게 함께 구성할지 정리한다 (docling-serve 방식 준용).

## 사전 확인 결과 (완료)

| 항목 | 결과 |
|---|---|
| Docker 데몬 | 실행 중 (28.3.0) |
| `agentx-net` 외부 네트워크 | **없음** → 생성 필요 (compose가 `external: true`로 참조) |
| 이미지 빌드 비용 | ubuntu24.04 + libreoffice + default-jdk + nanum 폰트 → 최초 빌드 수 분~십수 분 예상 |
| 테스트 파일 | `hwpparser/data/sample.hwp` 실물 존재. 추가로 `강선우(2025)` 등 실제 공문서 폴더 존재 |
| 서비스 포트 | 호스트 40000 → 컨테이너 8000 |

## Phase A — 실서비스 E2E 테스트

### A-1. 컨테이너 기동
```bash
docker network create agentx-net        # 없는 외부 네트워크 생성 (compose 파일 무수정)
cd /Users/sangmoonjeon/project/hwpparser
docker compose up -d --build            # 최초 빌드 포함
```
- 판정: `docker compose ps`에서 healthy, `curl http://localhost:40000/health` → `{"status":"ok"}`
- 빌드 실패 시: 로그 확인 후 원인 보고 (Dockerfile은 수정하지 않음. 필요 시 사용자와 상의)

### A-2. 서비스 단독 기준선(baseline) 확인 — 컴포넌트 배제
```bash
curl -s -X POST http://localhost:40000/hwp2html/clean -F "file=@data/sample.hwp" -o /tmp/baseline.html
curl -s -X POST http://localhost:40000/hwp2md/convert -F "file=@data/sample.hwp" -o /tmp/baseline.md
```
- 목적: 이후 컴포넌트 결과와 비교할 기준. 서비스 자체 문제와 컴포넌트 문제를 분리.

### A-3. 컴포넌트 E2E 실행
- 기존 검증 스크립트를 실서비스용으로 확장 (스크래치패드에 작성, 저장소 오염 없음):
  - `HWPParserRemote(api_url="http://localhost:40000")` × {HTML, Markdown} × {sample.hwp, 자체 생성 sample.hwpx}
  - 검증 항목:
    1. 컴포넌트 결과 == A-2 기준선 (바이트 비교가 아닌 내용 비교)
    2. 표 구조 보존: HTML 출력에 `<table>` + `colspan`/`rowspan` 존재 여부 (plan.md의 핵심 요구)
    3. 한글 인코딩 깨짐 없음
    4. `timeout=120` 기본값으로 충분한지 (변환 소요 시간 기록)
- 실패 시: 컴포넌트 결함이면 수정 후 재검증. 서비스 결함이면 보고만 (hwpparser 저장소는 수정하지 않음).

### A-4. (선택) UI 확인
- `LFX_DEV=1 make backend` + `make frontend` → 캔버스에서 HWP Parser → Chat Output 연결 실행.
- 자동화 불가한 수동 단계이므로 안내만 제공.

## Phase B — Langflow 배포 관점 구성안

### 구성 원칙 (docling-serve 패턴 준용)
- **Langflow는 파서 컨테이너를 띄워주지 않는다.** 파서는 별도 서비스로 배포하고, 컴포넌트는 `api_url`로 접속만 한다.
- 이미 컴포넌트에 반영된 것: `transform_localhost_url` 사용 — Langflow가 컨테이너 안에서 돌 때 `localhost`를 `host.docker.internal`(또는 게이트웨이 IP)로 자동 치환 (`lfx/utils/util.py:119` 확인 완료).

### 시나리오별 api_url

| 배포 형태 | api_url 입력값 | 비고 |
|---|---|---|
| ① 개발: Langflow 호스트 실행 + 파서 도커 | `http://localhost:40000` | 지금 E2E와 동일 |
| ② 운영: 둘 다 도커, 같은 compose/네트워크 | `http://hwp_parser:8000` | 서비스명 DNS, 포트는 컨테이너 내부 포트 |
| ③ 혼합: Langflow 도커 + 파서 호스트/별도 | `http://localhost:40000` 그대로 | transform_localhost_url이 자동 처리 |

### 산출물: 통합 compose 예시 작성
아래 예시를 **plan 검토 후** 파일로 만든다. 위치는 검토 항목 ③ 참고.

```yaml
# langflow + hwp_parser 통합 배포 예시
services:
  langflow:
    image: langflowai/langflow:latest
    ports: ["7860:7860"]
    networks: [hwp-net]
    environment:
      - LANGFLOW_DATABASE_URL=...   # 운영 시 postgres 권장
  hwp_parser:
    build: /path/to/hwpparser
    networks: [hwp-net]
    # 호스트 포트 노출 불필요 — langflow가 서비스명으로 내부 접근
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"]
networks:
  hwp-net:
```

### 운영 시 검토 포인트 (문서에 기록만, 구현은 범위 밖)
- 파서의 soffice는 단일 인스턴스 — 동시 요청 처리량이 낮음. 대량 인덱싱 시 파서 레플리카/큐 필요.
- 파일 크기 제한과 timeout 정책 (컴포넌트 기본 120s).
- 폐쇄망 요구(plan.md) → 이미지 사전 빌드 후 프라이빗 레지스트리 배포.

## 산출물 목록

| # | 산출물 | 위치 |
|---|---|---|
| 1 | E2E 검증 스크립트 + 결과 리포트 | 스크래치패드 (저장소 외부) |
| 2 | 컴포넌트 수정 (E2E에서 결함 발견 시에만) | `hwp_parser_remote.py` |
| 3 | 통합 compose 예시 파일 | **검토 항목 ③** |
| 4 | 배포 가이드 요약을 학습 노트에 추가 | `langflow-architecture-mapping.md` 또는 신규 노트 |

## 리스크와 정리(cleanup)

- 최초 이미지 빌드가 길 수 있음 (LibreOffice 설치). 빌드는 백그라운드로 돌리고 진행 상황 보고.
- 빌드 실패 가능 지점: H2Orestart Java 빌드, apt 미러 속도.
- 테스트 후 컨테이너는 **기본적으로 유지** (UI 확인용) — 원하시면 `docker compose down`으로 정리. 생성한 `agentx-net`도 정리 대상.
- langflow 저장소에는 컴포넌트 파일 외 추가 변경 없음. hwpparser 저장소는 일절 수정하지 않음.

## 실행 결과 (2026-07-06)

| 문서 | 포맷 | 기준선 일치 | 표/병합 보존 | 인코딩 | 소요 |
|---|---|---|---|---|---|
| sample.hwp (1.6MB) | HTML | ✅ | ✅ table+span | ✅ | 4.2s |
| sample.hwp | Markdown | ✅ | — | ✅ | 8.3s |
| 의원실 양식.hwp | HTML | ✅ | ✅ | ✅ | 0.2s |
| 의원실 양식.hwp | Markdown | ✅ | — | ✅ | 0.2s |
| 입법계획 현황.hwpx | HTML | ✅ | ✅ rowspan=5 확인 | ✅ | 0.2s |
| 입법계획 현황.hwpx | Markdown | ✅ | — | ✅ | 0.1s |

- inline `HWPXTextExtractor`도 실물 hwpx에서 문단 47개 정상 추출 (불릿 위계 문자 □ 보존).
- 기본 timeout 120s는 1.6MB 문서(최대 8.3s)에 충분.
- **사용 지침**: 병합표가 중요한 RAG 용도는 HTML 포맷 권장 — Markdown 표는 rowspan을 표현하지 못해 병합 셀이 빈칸으로 나온다 (sapie plan.md의 "표는 Markdown 금지" 원칙과 일치하는 관찰).
- 변환 결과물: 스크래치패드 `out/` (sample.html 등 6종 + hwpx_inline_paragraphs.txt)

## 추가 실행 (2026-07-06): 시나리오 ② 실배포 완료

사용자 요청으로 개발 서버(7861/3000)를 내리고, 기존 `docker_example` 스택을 단일 환경으로 재구성:

- `docker_example/docker-compose.override.yml` 신설 (원본 compose 무수정):
  - `LANGFLOW_COMPONENTS_PATH=/app/custom_components` + 컴포넌트 소스 2개 파일을 읽기 전용 마운트 → 이미지 재빌드 없이 공식 이미지에서 커스텀 컴포넌트 로드
  - langflow 컨테이너를 `agentx-net`에 연결 → HWP Parser의 api_url로 `http://hwp_parser:8000` 사용 가능 (컨테이너 간 직결 확인 완료)
- `docker compose down`(볼륨 보존) 후 `up -d` — 기존 플로우/DB 유지
- 검증: `/api/v1/all`에 두 컴포넌트 탑재 확인 (`ext:data_source:...@extra` — 외부 경로 로드 방식의 명명), 컨테이너 간 `hwp_parser:8000/health` 200 OK
- 컴포넌트 소스를 수정하면 `docker compose restart langflow`만으로 반영됨

## 검토 요청 사항 (답 주시면 반영 후 진행)

1. **네트워크**: 없는 `agentx-net`을 `docker network create`로 만들어 compose 무수정으로 진행 — 동의하십니까? (대안: override 파일 작성)
2. **포트**: 호스트 40000 그대로 사용해도 됩니까? (충돌 시 대안 필요)
3. **compose 예시 파일 위치**: ⓐ hwpparser 저장소에 `deploy/langflow-compose.example.yml`로 추가 (타 프로젝트 파일 생성이라 확인 필요) / ⓑ langflow 쪽 학습 노트 옆에 예시로만 보관 / ⓒ 파일 없이 계획서 내 예시로 충분
4. **실제 공문서 테스트**: `data/강선우(2025)` 등 실제 문서 폴더가 보이는데, sample.hwp 외에 이 중 1건도 E2E에 포함할까요? (민감 문서라면 제외)

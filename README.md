# CRK Payment Gateway

CRK Payment Gateway는 카드 단말기(CAT)와 연동되는 결제 게이트웨이 애플리케이션입니다. 하나의 프로세스에서 다음 두 가지 인터페이스를 함께 제공합니다.

- Node 등 상위 애플리케이션이 호출하는 HTTP API 서버
- 카드 단말기와 직접 통신하는 TCP 서버

애플리케이션은 FastAPI 기반 REST API, SSE(Server-Sent Events) 스트림, 단말기와의 비동기 통신 처리, 정상 종료를 위한 graceful shutdown 절차를 포함합니다.

## 주요 기능

- 토큰 결제 승인 및 취소
- 삼성페이 승인 및 취소
- 카드 단말기 상태 확인
- 단말기 이벤트를 위한 SSE 스트림 제공
- 환경변수 기반 설정 관리
- 로깅 포맷 및 레벨 설정 지원

## 실행 요구사항

- Python 3.14 이상
- `uv`(Astral uv) 설치

`uv`가 설치되어 있지 않다면 먼저 공식 안내에 따라 설치해야 합니다.

- https://docs.astral.sh/uv/

설치 확인 예시는 다음과 같습니다.

```bash
uv --version
```

## 빠른 시작

프로젝트 루트 디렉토리에서 아래 순서로 실행합니다.

### 1. 의존성 설치

```bash
uv sync
```

### 2. 애플리케이션 실행

```bash
uv run src/main.py
```

애플리케이션이 시작되면 다음 서비스가 함께 실행됩니다.

- API 서버: `API_HOST:API_PORT`
- CAT TCP 서버: `CAT_HOST:CAT_PORT`

기본값 기준으로는 다음과 같습니다.

- API 서버: `127.0.0.1:8001`
- CAT TCP 서버: `0.0.0.0:5000`

## 환경변수 설정

설정은 [src/config.py](src/config.py)에서 로드되며, 별도 설정 파일 없이 환경변수로 주입합니다.

### 핵심 네트워크 설정

Node 애플리케이션이 접근하는 API 서버와 카드 단말기가 접속하는 CAT 서버 설정이 가장 중요합니다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `API_HOST` | `127.0.0.1` | HTTP API 서버 바인드 주소. Node 또는 다른 상위 서비스가 이 주소로 접근합니다. |
| `API_PORT` | `8001` | HTTP API 서버 포트 |
| `CAT_HOST` | `0.0.0.0` | 카드 단말기(CAT) TCP 서버 바인드 주소 |
| `CAT_PORT` | `5000` | 카드 단말기(CAT) TCP 서버 포트 |

### 전체 환경변수 목록

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `COMM_TIMEOUT` | `30.0` | 단말기 응답 대기 시간(초) |
| `SHUTDOWN_TIMEOUT` | `10.0` | graceful shutdown 시 작업 종료 대기 시간(초) |
| `API_HOST` | `127.0.0.1` | HTTP API 서버 바인드 주소 |
| `API_PORT` | `8001` | HTTP API 서버 포트 |
| `CAT_HOST` | `0.0.0.0` | 카드 단말기 TCP 서버 바인드 주소 |
| `CAT_PORT` | `5000` | 카드 단말기 TCP 서버 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨. `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` 중 하나 |
| `LOG_FORMAT` | `text` | 로그 포맷. `text` 또는 `json` |

### Linux/macOS 예시

```bash
export API_HOST=0.0.0.0
export API_PORT=8001
export CAT_HOST=0.0.0.0
export CAT_PORT=5000
export COMM_TIMEOUT=30
export SHUTDOWN_TIMEOUT=10
export LOG_LEVEL=INFO
export LOG_FORMAT=text

uv run src/main.py
```

## 운영 관점에서의 포트 의미

### API 서버

API 서버는 외부 애플리케이션이 호출하는 진입점입니다. 일반적으로 Node 서버가 이 주소와 포트로 결제 승인, 취소, 상태 확인 요청을 보냅니다.

- 기본 바인드 주소: `127.0.0.1`
- 기본 포트: `8001`

같은 머신의 Node 프로세스만 접근하면 충분한 경우에는 기본값을 유지하면 됩니다. 외부 호스트나 컨테이너 네트워크에서 접근해야 한다면 `API_HOST=0.0.0.0`처럼 명시적으로 변경해야 합니다.

### CAT TCP 서버

CAT 서버는 카드 단말기가 직접 접속하는 TCP 리스너입니다.

- 기본 바인드 주소: `0.0.0.0`
- 기본 포트: `5000`

단말기가 네트워크를 통해 연결해야 하므로, 일반적으로는 단말기가 도달 가능한 인터페이스와 포트를 열어 두어야 합니다. 방화벽, 라우팅, 단말기 설정값이 `CAT_HOST`와 `CAT_PORT`에 맞는지 함께 확인해야 합니다.

> 카드 단말기와 CAT 서버가 서로 통신해야 하므로, 두 기기는 같은 서브넷에 존재하여야 합니다.
> 이 때, 카드 단말기가 클라이언트로써 작동하므로 카드 단말기를 조작하여 CAT 서버 엔드포인트를 설정해주어야 합니다.
> DHCP 기반의 IP 설정을 진행하는 경우, 현재는 CAT 서버의 IP가 게이트웨이의 IP로 설정이 되므로 고정 IP 설정이 필수입니다.

## API 개요

애플리케이션은 다음 HTTP 엔드포인트를 제공합니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/status` | 카드 단말기 상태 확인 |
| `POST` | `/payment/token/approve` | 토큰 결제 승인 |
| `POST` | `/payment/token/cancel` | 토큰 결제 취소 |
| `POST` | `/payment/samsung-pay/approve` | 삼성페이 승인 |
| `POST` | `/payment/samsung-pay/cancel` | 삼성페이 취소 |
| `GET` | `/sse` | 단말기 이벤트 SSE 스트림 |

FastAPI 기본 문서 UI는 실행 후 다음 경로에서 확인할 수 있습니다.

- `/docs`
- `/openapi.json`

예를 들어 기본 설정으로 실행했다면 API 문서 주소는 다음과 같습니다.

- `http://127.0.0.1:8001/docs`

## 동작 구조

애플리케이션은 시작 시 세 가지 비동기 작업을 동시에 실행합니다.

- CAT 단말기 TCP 서버 실행
- 단말기 이벤트 처리용 Action Manager 실행
- 외부 연동용 FastAPI 서버 실행

종료 시에는 `SIGINT`, `SIGTERM` 등을 감지하여 등록된 작업을 순차적으로 정리하고, 설정된 `SHUTDOWN_TIMEOUT` 내에서 graceful shutdown을 수행합니다.

## 로깅

로그는 환경변수로 제어할 수 있습니다.

- `LOG_LEVEL`: 출력 레벨 제어
- `LOG_FORMAT=text`: 사람이 읽기 쉬운 텍스트 로그
- `LOG_FORMAT=json`: 운영 환경 수집용 구조화 로그

## 개발 메모

- 프로젝트 진입점은 [src/main.py](src/main.py)입니다.
- 환경변수 정의와 검증은 [src/config.py](src/config.py)에서 수행합니다.
- API 스펙은 [src/api/manager.py](src/api/manager.py)와 [src/api/schemas.py](src/api/schemas.py)에 정의되어 있습니다.

## 문제 해결

### `uv` 명령을 찾을 수 없는 경우

`uv`가 설치되어 있지 않거나 PATH에 등록되지 않은 상태입니다. `uv --version`으로 확인한 뒤, 공식 설치 문서를 참고해 다시 설치합니다.

### Node에서 API에 접근할 수 없는 경우

다음을 우선 확인합니다.

- `API_HOST`가 외부 접근 가능한 주소로 설정되어 있는지
- `API_PORT`가 기대한 포트와 일치하는지
- 해당 포트가 방화벽 또는 컨테이너 네트워크 정책에 의해 차단되지 않았는지

### 카드 단말기가 접속하지 못하는 경우

다음을 우선 확인합니다.

- `CAT_HOST`, `CAT_PORT`가 단말기 설정과 일치하는지
- 단말기에서 서버 머신으로 네트워크 접근이 가능한지
- 서버 측 방화벽이 TCP 포트를 허용하는지
- 다른 프로세스가 동일 포트를 이미 사용 중이지 않은지

# Mac mini 쿠팡·네이버 스크래퍼

OCI 백엔드 대신 집에 있는 Mac mini(Tailnet) 에서 구동되는 경량 scraper.
Akamai/네이버 captcha 를 우회하기 위해 수동 로그인된 Chrome 인스턴스에 CDP 로 붙어 동작한다.

## 아키텍처

2-tier 페치 구조:

1. **HTTP fast path** — `curl_cffi.AsyncSession(impersonate="chrome131")` + Chrome 세션쿠키 (`_abck`, `bm_*` 등) 로 HTML 직빵. 200ms~1s.
2. **nodriver fallback** — HTTP 가 403/empty 일 때만 실제 Chrome 탭을 열어 처리. 캐시 쿠키 리프레시 겸용.

두 경로 모두 JSON-LD(`<script type="application/ld+json">`) 기반 파싱. 네이버 스마트스토어는 `__PRELOADED_STATE__` / `__NEXT_DATA__` 파싱.

## 구성 요소

- `app.py` — FastAPI uvicorn 엔드포인트 (`/healthz`, `/coupang/search`, `/coupang/detail`, `/naver/detail`).
- `launch_scraper.sh` — launchctl 에서 호출하는 런처. Chrome CDP 보장 후 uvicorn 기동.
- `requirements.txt` — Python 3.12+ 의존성.

## Mac mini 배포 절차 (최초 1회)

```bash
# 1. Python 3.12 venv (ollama 관련 X)
/opt/homebrew/bin/python3.12 -m venv /Users/hj/scraper-venv-nodriver
/Users/hj/scraper-venv-nodriver/bin/pip install -r requirements.txt

# 2. 소스 배치
mkdir -p /Users/hj/scraper-nodriver
cp app.py launch_scraper.sh /Users/hj/scraper-nodriver/
chmod +x /Users/hj/scraper-nodriver/launch_scraper.sh

# 3. Chrome CDP 런처 (/Users/hj/scraper/launch_chrome_cdp.sh) 는 기존 것 재사용

# 4. launchctl plist
# ~/Library/LaunchAgents/com.hj.scraper.plist 의 ProgramArguments 를
# /Users/hj/scraper-nodriver/launch_scraper.sh 로 지정

launchctl load ~/Library/LaunchAgents/com.hj.scraper.plist
curl -sS http://localhost:8081/healthz
```

## 업데이트 절차

```bash
# repo 에서 최신 소스 받고 교체
scp app.py hj:/Users/hj/scraper-nodriver/app.py
ssh hj "launchctl kickstart -k gui/\$(id -u)/com.hj.scraper"
```

## 기술적 주의사항

- **impersonate 프로필과 UA 일치 필수**: `HTTP_IMPERSONATE = "chrome131"` 로 두고 User-Agent 를 수동 override 하지 말 것. Chrome TLS fingerprint 와 UA 문자열 Chrome 버전이 어긋나면 Akamai 가 403 던진다.
- **Chrome 120+ `sameParty` 제거**: nodriver 의 `cdp.network.Cookie.from_json` 이 이 필드를 hard-require 하므로 app.py 상단에서 monkey-patch 로 누락 시 기본값 주입.
- **탭 세마포어**: nodriver 폴백은 `_page_lock = Semaphore(3)` 로 병렬 3 탭. HTTP fast-path 는 `_http_sem = Semaphore(6)` 로 동시 6 커넥션.
- **Naver captcha**: 스마트스토어 상세는 captcha 가 간헐적으로 걸린다. 걸리면 수동으로 Chrome 창 열어 captcha 풀고 세션 유지.

## 엔드포인트 계약 (백엔드에서 호출)

OCI 백엔드의 `coupang_scraper_url` 이 가리키는 대상. 변경되면 백엔드 `backend/app/collectors/remote_scraper.py` 도 같이 수정해야 한다.

```
GET  /healthz
GET  /coupang/search?q=<keyword>&limit=<n>
POST /coupang/detail   {"url": "https://www.coupang.com/vp/products/..."}
POST /naver/detail     {"url": "https://smartstore.naver.com/main/products/..."}
```

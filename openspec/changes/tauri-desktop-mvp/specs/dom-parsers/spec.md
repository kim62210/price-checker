## ADDED Requirements

### Requirement: 쿠팡 상세 페이지 파싱

시스템은 쿠팡 상세 페이지(`https://www.coupang.com/vp/products/<id>`)에서 가격·배송비·옵션 정보를 파싱해야 한다(MUST). 파싱 우선순위는:
1. `<script type="application/ld+json">` JSON-LD 의 `offers.price`, `offers.priceCurrency`, `offers.availability`.
2. `<meta property="product:price:amount">`, `<meta property="og:price:amount">` (JSON-LD 미존재 시 백업).
3. 페이지 내 `.price-value`, `.total-price` 등 selector 기반 텍스트 추출(최후 폴백).

배송비는 로켓/일반 배송 라벨과 "무료배송", "N,NNN원 배송" 텍스트 패턴으로 추출하고, 쿠팡 로켓 19,800원 임계치는 Rust 측 `shipping_policy` 에서 최종 반영한다.

#### Scenario: JSON-LD 가 존재한다
- **WHEN** 쿠팡 상세 페이지에 `offers.price: "12900"` 이 포함된 JSON-LD 가 있다
- **THEN** 파서는 `{ price: 12900, currency: "KRW", source: "json_ld" }` 를 반환한다

#### Scenario: JSON-LD 가 없고 meta tag 만 있다
- **WHEN** JSON-LD 는 없고 `<meta property="product:price:amount" content="15800">` 만 있다
- **THEN** 파서는 `{ price: 15800, currency: "KRW", source: "meta_tag" }` 를 반환한다

#### Scenario: 옵션 배열 추출
- **WHEN** 쿠팡 상세에 옵션별 가격이 여러 개 있다
- **THEN** 파서는 각 옵션을 `{ option_text: string, price: number, option_id: string | null }` 배열로 반환한다

### Requirement: 네이버 스마트스토어 상세 페이지 파싱

시스템은 네이버 스마트스토어 상세 페이지에서 `window.__PRELOADED_STATE__` JSON 트리를 추출해 가격·옵션·배송정보를 파싱해야 한다(MUST). 접근 경로는 `productDetail.A.product` 하위의 `salePrice`, `options`, `shippingInfo`, `sellerId`, `freeShippingPrice` (셀러별 무료배송 임계치).

#### Scenario: __PRELOADED_STATE__ 추출
- **WHEN** 네이버 스마트스토어 상세가 로드되었다
- **THEN** 파서는 `window.__PRELOADED_STATE__` 가 정의될 때까지 최대 10초 폴링 후 JSON 을 추출한다

#### Scenario: 옵션별 가격 추출
- **WHEN** 상품에 용량·수량별 옵션이 여러 개 정의되어 있다
- **THEN** 파서는 `options[]` 배열에서 각 옵션의 `salePrice`, `optionName`, `stock` 을 추출해 정규화된 배열로 반환한다

#### Scenario: 셀러 무료배송 임계치
- **WHEN** 상세 페이지에 `freeShippingPrice: 30000` 이 설정되어 있다
- **THEN** 파서는 `{ shipping_fee: 3000, free_threshold: 30000 }` 을 반환하고 Rust 의 `shipping_policy` 가 실결제 합산으로 최종 배송비 0/3000원을 결정한다

### Requirement: 파서 결과 스키마

모든 파서는 공통 TypeScript 인터페이스 `ParsedProduct` 를 준수해야 한다(MUST):
```typescript
interface ParsedProduct {
  platform: "coupang" | "naver";
  product_id: string;
  title: string;
  options: Array<{
    option_text: string;
    price: number;
    option_id: string | null;
    stock: number | null;
  }>;
  shipping: {
    fee: number;
    free_threshold: number | null;
    is_rocket: boolean;
    source: "json_ld" | "meta_tag" | "selector" | "preloaded_state";
  };
  parser_version: string;
  parsed_at: string;
}
```

결과는 `window.__PARSER_RESULT__` 전역에 세팅되며, Rust 측은 `webview.eval("JSON.stringify(window.__PARSER_RESULT__)")` 로 회수해 `serde_json` 으로 역직렬화한다.

#### Scenario: 스키마 준수
- **WHEN** 어떤 파서든 파싱을 완료한다
- **THEN** 결과는 위 `ParsedProduct` 인터페이스의 모든 필드를 포함하며, 누락/null 필드는 명시적으로 `null` 로 세팅된다

#### Scenario: Rust 역직렬화 실패
- **WHEN** `window.__PARSER_RESULT__` 가 스키마를 위반한다
- **THEN** Rust 는 `parser_failed` 에러를 반환하고 원본 JSON 을 로그에 기록한다

### Requirement: 주입 및 결과 회수 프로토콜

파서 주입과 결과 회수는 다음 프로토콜을 따라야 한다(MUST):
1. Rust 는 먼저 `webview.eval("window.__PARSER_RESULT__ = null;")` 로 플래그 초기화.
2. Rust 는 사전 번들된 파서 JS 문자열을 `webview.eval()` 로 주입.
3. Rust 는 200ms 간격으로 `webview.eval("JSON.stringify(window.__PARSER_RESULT__)")` 를 폴링, 최대 10초.
4. 결과가 `null` 이 아니면 `serde_json::from_str` 로 역직렬화하고 반환.
5. 10초가 지나도 결과가 없으면 `parser_failed` 반환.

Tauri 2.x 의 webview → host IPC 경로(`window.__TAURI__.event.emit`) 가 사용 가능하면 폴링 대신 이벤트 기반으로 교체한다 [교차검증 필요 — 공식 docs 재확인].

#### Scenario: 200ms 폴링으로 회수
- **WHEN** 파서가 주입 후 1.2초 만에 결과를 세팅한다
- **THEN** Rust 는 6번째 폴링에서 결과를 회수한다 (200ms × 6 = 1200ms)

#### Scenario: 10초 타임아웃
- **WHEN** 파서가 10초 동안 결과를 세팅하지 못한다
- **THEN** Rust 는 `parser_failed` 를 반환하고 WebView 를 파괴한다

### Requirement: 파서 버전 관리

모든 파서 결과에는 `parser_version` 문자열(예: `"coupang:1.2.0"`, `"naver:1.0.5"`)이 포함되어야 한다(MUST). 이는 백엔드에 결과 업로드 시 함께 전송되어, 향후 DOM 구조 변경으로 인한 파싱 실패율 추적과 핫픽스 배포 판단에 사용된다.

#### Scenario: 버전 태깅
- **WHEN** `coupang-parser.ts` 가 v1.2.0 로 빌드되었다
- **THEN** 모든 쿠팡 파싱 결과에 `parser_version: "coupang:1.2.0"` 이 포함된다

#### Scenario: 백엔드 업로드
- **WHEN** 앱이 `POST /api/v1/procurement/results` 로 결과를 업로드한다
- **THEN** 각 항목의 `parser_version` 이 payload 에 포함되어 백엔드가 버전별 실패율을 집계할 수 있다

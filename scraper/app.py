"""쿠팡·네이버 공용 미니 스크래퍼 — nodriver 포팅 버전.

Playwright connect_over_cdp 대신 nodriver.start(host, port) 로 기존 Chrome 에 어태치한다.
CDP 레이어는 동일하므로 엔드포인트 계약은 100% 유지 (OCI 백엔드 호환성).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import nodriver
from curl_cffi.requests import AsyncSession
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Chrome 120+ 은 CDP 쿠키 응답에 'sameParty' 필드를 더 이상 보내지 않는다.
# nodriver의 cdp.network.Cookie.from_json 은 이 키를 hard-require 하므로
# 누락 시 기본값을 주입하도록 monkey-patch.
from nodriver.cdp import network as _nw_cdp  # noqa: E402

_original_cookie_from_json = _nw_cdp.Cookie.from_json


@classmethod
def _patched_cookie_from_json(cls, json):  # type: ignore[no-redef]
    json.setdefault("sameParty", False)
    return _original_cookie_from_json.__func__(cls, json)


_nw_cdp.Cookie.from_json = _patched_cookie_from_json

logger = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

CDP_URL = os.environ.get("SCRAPER_CDP_URL", "http://localhost:9222")
COUPANG_BASE = "https://www.coupang.com"
BLOCK_MARKERS = (
    "access denied",
    "pardon our interruption",
    "sorry! access denied",
    "sec-if-cpt-container",
    "errors.edgesuite.net",
)
WARMUP_TTL_SEC = int(os.environ.get("SCRAPER_WARMUP_TTL", "600"))
DEFAULT_TIMEOUT_SEC = 30.0
POST_NAV_IDLE_SEC = 1.2

HTTP_FETCH_TIMEOUT_SEC = 8.0
# curl_cffi impersonate 프로필 — UA/헤더/TLS 전부 프로필이 제공하므로 User-Agent 를 수동으로 덮지 말 것.
# 수동 UA 로 덮으면 TLS fingerprint(chrome124) 와 Accept 헤더(Chrome/147) 가 불일치 → Akamai 403.
HTTP_IMPERSONATE = "chrome131"

# 쿠팡 상세 페이지는 `<script c="" src="product" type="application/ld+json">` 처럼
# type 속성 앞에 다른 attr 이 붙는 경우가 있어 `\s+type=` 로 타이트하게 제약하면 놓친다.
_LD_SCRIPT_RE = re.compile(
    r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class ListingItem(BaseModel):
    platform_product_id: str
    raw_title: str
    product_url: str
    representative_price: int | None = None
    thumbnail_url: str | None = None
    is_rocket: bool = False
    vendor_item_id: str | None = None
    item_id: str | None = None
    rating: float | None = None
    review_count: int | None = None


class SearchResponse(BaseModel):
    query: str
    items: list[ListingItem]


class OptionItem(BaseModel):
    platform_option_id: str | None = None
    option_name_text: str
    attrs: dict[str, str] = Field(default_factory=dict)
    price: int
    stock: int | None = None
    usable: bool = True


class DetailResponse(BaseModel):
    options: list[OptionItem]
    shipping_fee: int = 0
    shipping_confidence: str = "unknown"
    free_shipping_threshold: int | None = None
    fetch_method: str = "cdp"
    raw_title: str | None = None


class DetailRequest(BaseModel):
    url: str


_browser: nodriver.Browser | None = None
# nodriver 폴백 경로: 탭 3개 동시 허용 (Chrome CDP multi-tab safe)
_page_lock = asyncio.Semaphore(3)
# HTTP fast-path: 동시 curl_cffi 요청 6개까지
_http_sem = asyncio.Semaphore(6)
_last_warmup: float = 0.0


def _parse_cdp_endpoint(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 9222
    return host, port


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _browser
    host, port = _parse_cdp_endpoint(CDP_URL)
    logger.info("connecting to CDP host=%s port=%d", host, port)
    _browser = await nodriver.start(host=host, port=port)
    logger.info("connected targets=%d", len(_browser.targets))
    try:
        yield
    finally:
        _browser = None


app = FastAPI(title="price-tracker-scraper-nodriver", lifespan=lifespan)


async def _eval(tab: nodriver.Tab, expr: str) -> Any:
    """return_by_value=True 로 평가 후 falsy 결과가 RemoteObject 로 떨어지는 nodriver 쿼크 흡수.
    주의: array/object 반환은 RemoteObject 로 떨어지므로 _eval_json() 사용.
    """
    result = await tab.evaluate(expr, return_by_value=True)
    if hasattr(result, "value"):
        return result.value
    return result


async def _eval_json(tab: nodriver.Tab, expr: str) -> Any:
    """array/object 를 반환하는 표현식은 JSON.stringify 래퍼로 감싸 안정적으로 가져온다."""
    wrapped = f"JSON.stringify({expr})"
    raw = await tab.evaluate(wrapped, return_by_value=True)
    if hasattr(raw, "value"):
        raw = raw.value
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


async def _new_tab() -> nodriver.Tab:
    assert _browser is not None
    return await _browser.get("about:blank", new_tab=True)


async def _navigate(tab: nodriver.Tab, url: str, *, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
    """tab.get 후 document.readyState 폴링 + 추가 idle."""
    await tab.get(url)
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_sec
    while loop.time() < deadline:
        ready = await _eval(tab, "document.readyState")
        if ready in ("interactive", "complete"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(POST_NAV_IDLE_SEC)


async def _get_title(tab: nodriver.Tab) -> str:
    value = await _eval(tab, "document.title")
    return value or ""


async def _get_body_head(tab: nodriver.Tab, length: int = 4000) -> str:
    expr = f"document.body ? document.body.innerText.slice(0, {length}) : ''"
    value = await _eval(tab, expr)
    return value or ""


def _invalidate_warmup() -> None:
    global _last_warmup
    _last_warmup = 0.0


async def _ensure_warmup(tab: nodriver.Tab) -> None:
    global _last_warmup
    if time.time() - _last_warmup < WARMUP_TTL_SEC:
        return
    try:
        await _navigate(tab, COUPANG_BASE + "/")
        _last_warmup = time.time()
    except Exception:
        logger.exception("home visit failed")


def _is_blocked_title_html(title: str, body_text: str) -> bool:
    t = (title or "").lower()
    b = (body_text or "")[:4000].lower()
    return any(m in t or m in b for m in BLOCK_MARKERS)


async def _wait_for_ld(tab: nodriver.Tab, timeout_sec: float = 10.0) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_sec
    while loop.time() < deadline:
        count = await _eval(
            tab, 'document.querySelectorAll(\'script[type="application/ld+json"]\').length'
        )
        try:
            if count and int(count) > 0:
                return True
        except (TypeError, ValueError):
            pass
        await asyncio.sleep(0.2)
    logger.warning("JSON-LD not injected within %.1fs", timeout_sec)
    return False


async def _get_chrome_cookies(domain_suffix: str) -> dict[str, str]:
    """attached Chrome 에서 domain_suffix 에 해당하는 쿠키만 추출."""
    if _browser is None:
        return {}
    try:
        cookies = await _browser.cookies.get_all()
    except Exception:
        logger.exception("failed to read chrome cookies")
        return {}
    out: dict[str, str] = {}
    for c in cookies:
        domain = getattr(c, "domain", "") or ""
        if domain_suffix in domain and c.name and c.value:
            out[c.name] = c.value
    return out


async def _fetch_html_http(
    url: str,
    *,
    cookies: dict[str, str],
    referer: str = "https://www.coupang.com/",
    timeout: float = HTTP_FETCH_TIMEOUT_SEC,
) -> str | None:
    """curl_cffi 로 Chrome TLS fingerprint + 세션쿠키 매칭해 HTML 직빵.
    200 + 블록 마커 없으면 HTML 반환, 아니면 None (→ 호출측이 nodriver 로 fallback).
    주의: UA/Accept 등 주요 헤더는 impersonate 프로필이 제공하므로 Referer 만 덮어쓴다."""
    headers = {"Referer": referer}
    async with _http_sem:
        try:
            async with AsyncSession(impersonate=HTTP_IMPERSONATE) as s:
                resp = await s.get(url, cookies=cookies, headers=headers, timeout=timeout)
        except Exception as exc:
            logger.info("http_fetch_exception url=%s err=%s", url[:80], exc)
            return None
    if resp.status_code != 200:
        logger.info("http_fetch_non200 status=%d url=%s", resp.status_code, url[:80])
        return None
    body_head = (resp.text or "")[:4000].lower()
    if any(m in body_head for m in BLOCK_MARKERS):
        logger.info("http_fetch_blocked url=%s", url[:80])
        return None
    return resp.text


def _parse_ld_from_html(html: str) -> list[Any]:
    """HTML 문자열에서 JSON-LD 스크립트 regex 추출·파싱."""
    parsed: list[Any] = []
    for raw in _LD_SCRIPT_RE.findall(html):
        try:
            parsed.append(json.loads(raw.strip()))
        except json.JSONDecodeError:
            continue
    return parsed


async def _collect_ld(tab: nodriver.Tab) -> list[Any]:
    raw_list = await _eval_json(
        tab,
        '[...document.querySelectorAll(\'script[type="application/ld+json"]\')].map(s => s.textContent)',
    )
    parsed: list[Any] = []
    for raw in raw_list or []:
        try:
            parsed.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return parsed


def _flatten_ld(ld_list: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in ld_list:
        if isinstance(node, dict):
            if isinstance(node.get("@graph"), list):
                out.extend(x for x in node["@graph"] if isinstance(x, dict))
            else:
                out.append(node)
        elif isinstance(node, list):
            out.extend(x for x in node if isinstance(x, dict))
    return out


def _pick_type(nodes: list[dict[str, Any]], type_name: str) -> dict[str, Any] | None:
    for n in nodes:
        t = n.get("@type")
        if t == type_name:
            return n
        if isinstance(t, list) and type_name in t:
            return n
    return None


def _parse_product_url(url: str) -> tuple[str, str | None, str | None]:
    parsed = urlparse(url)
    path = parsed.path
    prod = ""
    if "/vp/products/" in path:
        prod = path.rsplit("/", 1)[-1]
    qs = parse_qs(parsed.query)
    item_id = qs.get("itemId", [None])[0]
    vendor_item_id = qs.get("vendorItemId", [None])[0]
    return prod, item_id, vendor_item_id


def _build_listing_items(ld_nodes: list[dict[str, Any]], limit: int) -> list[ListingItem]:
    collection = _pick_type(ld_nodes, "CollectionPage") or {}
    main = collection.get("mainEntity") if isinstance(collection.get("mainEntity"), dict) else None
    if not main:
        main = _pick_type(ld_nodes, "ItemList") or {}
    items_src = main.get("itemListElement") if isinstance(main.get("itemListElement"), list) else []

    out: list[ListingItem] = []
    for entry in items_src:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item") if isinstance(entry.get("item"), dict) else None
        if not item:
            continue
        url = item.get("url") or ""
        if not url:
            continue
        prod, item_id, vendor_item_id = _parse_product_url(url)
        if not prod:
            continue
        offers = item.get("offers") if isinstance(item.get("offers"), dict) else {}
        price_raw = offers.get("price") if offers else None
        try:
            price = int(float(price_raw)) if price_raw is not None else None
        except (TypeError, ValueError):
            price = None
        rating_obj = item.get("aggregateRating") if isinstance(item.get("aggregateRating"), dict) else {}
        rating_value = rating_obj.get("ratingValue")
        try:
            rating = float(rating_value) if rating_value is not None else None
        except (TypeError, ValueError):
            rating = None
        review_count_raw = rating_obj.get("reviewCount") or rating_obj.get("ratingCount")
        try:
            review_count = int(review_count_raw) if review_count_raw is not None else None
        except (TypeError, ValueError):
            review_count = None
        thumbnail = item.get("image")
        if isinstance(thumbnail, list):
            thumbnail = thumbnail[0] if thumbnail else None
        out.append(
            ListingItem(
                platform_product_id=prod,
                raw_title=str(item.get("name") or "").strip(),
                product_url=url,
                representative_price=price,
                thumbnail_url=thumbnail if isinstance(thumbnail, str) else None,
                is_rocket=False,
                vendor_item_id=vendor_item_id,
                item_id=item_id,
                rating=rating,
                review_count=review_count,
            )
        )
        if len(out) >= limit:
            break
    return out


def _extract_shipping_from_product(product_node: dict[str, Any]) -> tuple[int, str]:
    offers = product_node.get("offers") if isinstance(product_node.get("offers"), dict) else {}
    shipping = offers.get("shippingDetails") if isinstance(offers.get("shippingDetails"), dict) else None
    if not shipping:
        return 0, "unknown"
    rate = shipping.get("shippingRate") if isinstance(shipping.get("shippingRate"), dict) else None
    if not rate:
        return 0, "unknown"
    value_raw = rate.get("value")
    try:
        value = int(float(value_raw))
    except (TypeError, ValueError):
        return 0, "unknown"
    return value, "explicit"


def _extract_price(product_node: dict[str, Any]) -> int | None:
    offers = product_node.get("offers") if isinstance(product_node.get("offers"), dict) else {}
    price_raw = offers.get("price")
    try:
        return int(float(price_raw)) if price_raw is not None else None
    except (TypeError, ValueError):
        return None


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    # attach 모드에서는 _browser.stopped 가 항상 True 로 떨어지므로 connection 유무로 판별
    browser_ok = _browser is not None and _browser.connection is not None
    return {
        "status": "ok" if browser_ok else "degraded",
        "cdp_url": CDP_URL,
        "browser_connected": browser_ok,
        "targets": len(_browser.targets) if _browser else 0,
        "last_warmup_ts": _last_warmup,
        "engine": "nodriver",
    }


def _build_coupang_search_url(q: str, limit: int) -> str:
    effective_list_size = max(limit, 20)
    effective_list_size = min(effective_list_size, 60)
    return (
        f"{COUPANG_BASE}/np/search"
        f"?q={quote(q)}&listSize={effective_list_size}&channel=user"
    )


async def _coupang_search_browser(q: str, limit: int) -> SearchResponse:
    """nodriver 기반 폴백 경로."""
    assert _browser is not None
    url = _build_coupang_search_url(q, limit)
    async with _page_lock:
        tab = await _new_tab()
        title = ""
        try:
            await _ensure_warmup(tab)
            await _navigate(tab, url)
            title = await _get_title(tab)
            body_text_head = await _get_body_head(tab)
            if _is_blocked_title_html(title, body_text_head):
                _invalidate_warmup()
                raise HTTPException(status_code=502, detail="coupang_block_page")
            await _wait_for_ld(tab)
            ld_raw = await _collect_ld(tab)
        finally:
            try:
                await tab.close()
            except Exception:
                logger.exception("tab close failed")
    ld_nodes = _flatten_ld(ld_raw)
    items = _build_listing_items(ld_nodes, limit)
    if not items:
        logger.warning("no items parsed q=%s ld_count=%d title=%s", q, len(ld_nodes), (title or "")[:80])
    return SearchResponse(query=q, items=items)


@app.get("/coupang/search", response_model=SearchResponse)
async def coupang_search(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(20, ge=1, le=60),
):
    assert _browser is not None
    url = _build_coupang_search_url(q, limit)
    # fast-path: HTTP + Chrome cookies
    cookies = await _get_chrome_cookies(".coupang.com")
    if cookies:
        html = await _fetch_html_http(url, cookies=cookies, referer=COUPANG_BASE + "/")
        if html:
            ld_nodes = _flatten_ld(_parse_ld_from_html(html))
            items = _build_listing_items(ld_nodes, limit)
            if items:
                logger.info("coupang_search_http_ok q=%s items=%d", q, len(items))
                return SearchResponse(query=q, items=items)
            logger.info("coupang_search_http_empty q=%s falling_back", q)
    # slow-path: nodriver browser
    return await _coupang_search_browser(q, limit)


def _build_detail_from_product_node(
    product: dict[str, Any], url: str, *, fetch_method: str
) -> DetailResponse:
    price = _extract_price(product)
    if price is None:
        raise HTTPException(status_code=502, detail="product_price_missing")
    shipping_fee, shipping_conf = _extract_shipping_from_product(product)
    raw_title = str(product.get("name") or "").strip()
    prod_id, item_id, vendor_item_id = _parse_product_url(url)
    option_id = vendor_item_id or item_id or prod_id or None
    option = OptionItem(
        platform_option_id=option_id,
        option_name_text=raw_title,
        attrs={},
        price=price,
        stock=None,
        usable=True,
    )
    return DetailResponse(
        options=[option],
        shipping_fee=shipping_fee,
        shipping_confidence=shipping_conf,
        free_shipping_threshold=None,
        fetch_method=fetch_method,
        raw_title=raw_title,
    )


async def _coupang_detail_browser(url: str) -> DetailResponse:
    """nodriver 기반 폴백 경로."""
    assert _browser is not None
    async with _page_lock:
        tab = await _new_tab()
        try:
            await _ensure_warmup(tab)
            await _navigate(tab, url, timeout_sec=45.0)
            title = await _get_title(tab)
            body_text_head = await _get_body_head(tab)
            if _is_blocked_title_html(title, body_text_head):
                _invalidate_warmup()
                raise HTTPException(status_code=502, detail="coupang_block_page")
            await _wait_for_ld(tab, timeout_sec=12.0)
            ld_raw = await _collect_ld(tab)
        finally:
            try:
                await tab.close()
            except Exception:
                logger.exception("tab close failed")
    ld_nodes = _flatten_ld(ld_raw)
    product = _pick_type(ld_nodes, "Product")
    if not product:
        raise HTTPException(status_code=502, detail="product_json_ld_missing")
    return _build_detail_from_product_node(product, url, fetch_method="cdp")


@app.post("/coupang/detail", response_model=DetailResponse)
async def coupang_detail(req: DetailRequest):
    if "coupang.com" not in req.url:
        raise HTTPException(status_code=400, detail="not_a_coupang_url")
    assert _browser is not None
    # fast-path: HTTP + Chrome cookies
    cookies = await _get_chrome_cookies(".coupang.com")
    if cookies:
        html = await _fetch_html_http(req.url, cookies=cookies, referer=COUPANG_BASE + "/")
        if html:
            ld_nodes = _flatten_ld(_parse_ld_from_html(html))
            product = _pick_type(ld_nodes, "Product")
            if product:
                logger.info("coupang_detail_http_ok url=%s", req.url[:80])
                return _build_detail_from_product_node(product, req.url, fetch_method="http")
            logger.info("coupang_detail_http_no_product url=%s falling_back", req.url[:80])
    # slow-path: nodriver browser
    return await _coupang_detail_browser(req.url)


# --- 네이버 스마트스토어 상세 ---

_SMARTSTORE_STATE_RE = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*JSON\.parse\([\"'](.+?)[\"']\)\s*;", re.DOTALL
)
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _parse_naver_state(html: str) -> dict[str, Any] | None:
    m = _SMARTSTORE_STATE_RE.search(html)
    if m:
        try:
            raw = bytes(m.group(1), "utf-8").decode("unicode_escape")
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    m = _NEXT_DATA_RE.search(html)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _collect_naver_options(state: dict[str, Any]) -> list[OptionItem]:
    candidates: list[list[dict[str, Any]]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, list) and key in {
                    "optionCombinations",
                    "productOptionCombinations",
                    "optionSimpleList",
                }:
                    candidates.append([v for v in value if isinstance(v, dict)])
                elif isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(state)

    options: list[OptionItem] = []
    for bucket in candidates:
        for item in bucket:
            price_raw = item.get("price")
            if price_raw is None:
                continue
            try:
                price = int(price_raw)
            except (TypeError, ValueError):
                continue
            name_parts: list[str] = []
            for idx in range(1, 5):
                value = item.get(f"optionName{idx}")
                if value:
                    name_parts.append(str(value))
            option_text = " ".join(name_parts) or str(item.get("optionName") or "")
            if not option_text:
                continue
            stock_raw = item.get("stockQuantity")
            try:
                stock = int(stock_raw) if stock_raw is not None else None
            except (TypeError, ValueError):
                stock = None
            options.append(
                OptionItem(
                    platform_option_id=str(item.get("id")) if item.get("id") else None,
                    option_name_text=option_text,
                    attrs={f"axis_{i}": name_parts[i] for i in range(len(name_parts))},
                    price=price,
                    stock=stock if stock else None,
                    usable=bool(item.get("usable", True)),
                )
            )
    return options


def _extract_naver_shipping_fee(state: dict[str, Any]) -> int | None:
    def walk(obj: Any) -> int | None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"baseFee", "deliveryFee", "baseDeliveryFee"} and isinstance(
                    value, (int, float)
                ):
                    return int(value)
                found = walk(value)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found is not None:
                    return found
        return None

    return walk(state)


def _is_smartstore_url(url: str) -> bool:
    return "smartstore.naver.com" in url


@app.post("/naver/detail", response_model=DetailResponse)
async def naver_detail(req: DetailRequest):
    if not _is_smartstore_url(req.url):
        raise HTTPException(status_code=400, detail="not_smartstore_url")
    assert _browser is not None
    async with _page_lock:
        tab = await _new_tab()
        try:
            await _navigate(tab, req.url, timeout_sec=45.0)
            await asyncio.sleep(1.5)
            html = await tab.get_content()
            title = await _get_title(tab)
        finally:
            try:
                await tab.close()
            except Exception:
                logger.exception("tab close failed")

    state = _parse_naver_state(html)
    if state is None:
        logger.warning(
            "naver_state_missing url=%s title=%s", req.url, (title or "")[:80]
        )
        raise HTTPException(status_code=502, detail="naver_state_missing")

    options = _collect_naver_options(state)
    if not options:
        logger.warning("naver_options_missing url=%s", req.url)
        raise HTTPException(status_code=502, detail="naver_options_missing")

    shipping_fee_raw = _extract_naver_shipping_fee(state)
    shipping_fee = int(shipping_fee_raw) if shipping_fee_raw is not None else 0
    shipping_conf = "explicit" if shipping_fee_raw is not None else "unknown"

    return DetailResponse(
        options=options,
        shipping_fee=shipping_fee,
        shipping_confidence=shipping_conf,
        free_shipping_threshold=None,
        fetch_method="cdp",
        raw_title=title or None,
    )

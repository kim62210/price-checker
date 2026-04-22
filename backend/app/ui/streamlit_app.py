"""Streamlit 기반 내부 UI (모바일 반응형).

사용법: `streamlit run app/ui/streamlit_app.py`

백엔드 API(`/api/v1/search`)를 호출해 결과를 카드·표로 표시하고 CSV 다운로드를 제공한다.
좁은 뷰포트에서는 카드 레이아웃으로 자동 전환, 넓은 뷰포트에서는 카드+테이블을 함께 보여준다.
"""

from __future__ import annotations

import html
import os
from io import StringIO

import httpx
import pandas as pd
import streamlit as st

DEFAULT_API_BASE = os.getenv("LOWEST_PRICE_API_BASE", "http://localhost:8000")
PRIVATE_BANNER = (
    "비공개 친구용 도구 — 외부 공유 및 상용 목적 사용 금지. "
    "표시된 가격·배송비는 최종 플랫폼 페이지와 다를 수 있다."
)

RESPONSIVE_CSS = """
<style>
/* 컨테이너 여백 최적화 */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 1.2rem !important;
    max-width: 1100px !important;
}

/* 타이틀 반응형 */
h1 { font-size: clamp(1.15rem, 3.5vw, 1.75rem) !important; line-height: 1.25 !important; }
h2 { font-size: clamp(1rem, 2.8vw, 1.25rem) !important; }

/* 배너/알림 타이포 축소 */
.stAlert { font-size: 0.85rem !important; padding: 0.6rem 0.8rem !important; }

/* 메인 검색창 + 버튼 */
div[data-testid="stTextInput"] input { font-size: 1rem !important; }
div[data-testid="stButton"] > button { width: 100%; font-weight: 600; }

/* 결과 카드 */
.lp-card {
    border: 1px solid rgba(120, 120, 120, 0.25);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    background: rgba(250, 250, 250, 0.5);
}
.lp-card-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 6px;
}
.lp-card-title {
    font-weight: 600;
    font-size: 0.95rem;
    line-height: 1.35;
    flex: 1 1 65%;
    word-break: keep-all;
    overflow-wrap: anywhere;
}
.lp-card-title a { color: inherit; text-decoration: none; border-bottom: 1px dotted rgba(0,0,0,0.25); }
.lp-card-title a:hover { border-bottom-color: rgba(0,0,0,0.6); }
.lp-badge {
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
.lp-badge-naver   { background: #e7f5ec; color: #2a7f4a; }
.lp-badge-coupang { background: #ffece9; color: #c23b1a; }
.lp-badge-rocket  { background: #fff5dc; color: #9a6b00; }
.lp-card-unit {
    font-size: 1.08rem;
    font-weight: 700;
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
}
.lp-card-meta {
    font-size: 0.82rem;
    color: rgba(0,0,0,0.62);
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    font-variant-numeric: tabular-nums;
}
.lp-card-option {
    font-size: 0.78rem;
    color: rgba(0,0,0,0.55);
    margin-top: 4px;
    word-break: keep-all;
}

/* 다크 모드 보정 */
@media (prefers-color-scheme: dark) {
    .lp-card { background: rgba(40, 40, 42, 0.55); border-color: rgba(255,255,255,0.12); }
    .lp-card-meta { color: rgba(255,255,255,0.68); }
    .lp-card-option { color: rgba(255,255,255,0.55); }
    .lp-card-title a { border-bottom-color: rgba(255,255,255,0.28); }
}

/* 모바일 */
@media (max-width: 640px) {
    .block-container { padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
    .lp-card { padding: 10px 12px; }
    .lp-card-unit { font-size: 1rem; }
    .lp-card-title { font-size: 0.9rem; flex: 1 1 100%; }
    /* 모바일에서 테이블은 가로 스크롤 허용 */
    div[data-testid="stDataFrame"] { overflow-x: auto; }
}
</style>
"""


def _fetch(base: str, query: str, limit: int, force_refresh: bool) -> dict:
    with httpx.Client(base_url=base, timeout=httpx.Timeout(60.0, connect=3.0)) as client:
        response = client.get(
            "/api/v1/search",
            params={"q": query, "limit": limit, "force_refresh": force_refresh},
        )
        response.raise_for_status()
        return response.json()


def _results_to_df(payload: dict) -> pd.DataFrame:
    rows = payload.get("results") or []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    cols_preferred = [
        "platform",
        "unit_price_display",
        "display_base_value",
        "display_base_unit",
        "total_price",
        "price",
        "shipping_fee",
        "shipping_confidence",
        "unit_quantity",
        "unit",
        "raw_title",
        "option_name",
        "seller",
        "is_rocket",
        "parsed_confidence",
        "unit_price_confidence",
        "fetch_method",
        "detail_status",
        "product_url",
    ]
    existing = [c for c in cols_preferred if c in df.columns]
    return df[existing]


def _format_unit_display(row: dict) -> str:
    up = row.get("unit_price_display")
    if up:
        return str(up)
    base_v = row.get("display_base_value")
    base_u = row.get("display_base_unit")
    unit_price = row.get("unit_price")
    if unit_price is not None and base_v and base_u:
        return f"{int(round(unit_price)):,}원 / {base_v}{base_u}"
    if unit_price is not None:
        return f"{int(round(unit_price)):,}원"
    return "—"


def _render_cards(rows: list[dict]) -> None:
    for row in rows:
        platform = (row.get("platform") or "").lower()
        title = html.escape(row.get("raw_title") or "(제목 없음)")
        option_name = html.escape(row.get("option_name") or "")
        url = html.escape(row.get("product_url") or "#", quote=True)
        unit_display = html.escape(_format_unit_display(row))

        total = row.get("total_price") or 0
        price = row.get("price") or 0
        shipping = row.get("shipping_fee") or 0
        shipping_conf = row.get("shipping_confidence") or "unknown"
        is_rocket = bool(row.get("is_rocket"))
        seller = html.escape(row.get("seller") or "")

        platform_label = "네이버" if platform == "naver" else "쿠팡" if platform == "coupang" else platform.upper()
        badge_cls = f"lp-badge-{platform}" if platform in ("naver", "coupang") else ""

        rocket_badge = '<span class="lp-badge lp-badge-rocket">로켓</span>' if is_rocket else ""
        option_line = f'<div class="lp-card-option">{option_name}</div>' if option_name and option_name != title else ""
        seller_frag = f"<span>판매자: {seller}</span>" if seller else ""
        shipping_conf_frag = f" ({shipping_conf})" if shipping_conf and shipping_conf != "unknown" else ""

        card = f"""
<div class="lp-card">
  <div class="lp-card-head">
    <div class="lp-card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></div>
    <span class="lp-badge {badge_cls}">{platform_label}</span>
    {rocket_badge}
  </div>
  <div class="lp-card-unit">{unit_display}</div>
  <div class="lp-card-meta">
    <span>총 {int(total):,}원</span>
    <span>상품 {int(price):,}원</span>
    <span>배송 {int(shipping):,}원{shipping_conf_frag}</span>
    {seller_frag}
  </div>
  {option_line}
</div>
"""
        st.markdown(card, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="lowest-price",
        page_icon="🛒",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(RESPONSIVE_CSS, unsafe_allow_html=True)

    st.title("네이버·쿠팡 최저가 비교")
    st.caption(PRIVATE_BANNER)

    with st.sidebar:
        st.header("설정")
        api_base = st.text_input("API Base URL", value=DEFAULT_API_BASE)
        limit = st.slider("플랫폼당 수집 개수", 5, 40, 20, step=5)
        force_refresh = st.checkbox("캐시 무시", value=False)
        st.markdown("---")
        st.caption("좁은 화면에서는 카드 레이아웃을 권장. 넓은 화면에서는 아래 '전체 테이블'을 펼쳐 상세 컬럼을 확인.")

    query = st.text_input("검색어", placeholder="예: 코카콜라 500ml", label_visibility="collapsed")
    submit = st.button("검색", type="primary", disabled=not query.strip())

    if not submit:
        st.info("상단 검색창에 제품명을 입력해 검색하세요.")
        return

    with st.spinner("수집·파싱·정렬 중…"):
        try:
            payload = _fetch(api_base, query.strip(), limit, force_refresh)
        except httpx.HTTPError as exc:
            st.error(f"API 호출 실패: {exc}")
            return

    rows = payload.get("results") or []
    cached = payload.get("cached")
    sources = payload.get("sources", {}) or {}
    comparable = payload.get("comparable_group")

    st.success(f"완료 — {len(rows)}개 옵션 (cached={cached})")

    m1, m2, m3 = st.columns(3)
    m1.metric("Naver", str(sources.get("naver", "-")))
    m2.metric("Coupang", str(sources.get("coupang", "-")))
    m3.metric("Comparable", str(comparable if comparable is not None else "-"))

    if not rows:
        st.info("결과가 없습니다. 검색어를 바꾸거나 캐시 무시를 시도해 주세요.")
        return

    _render_cards(rows)

    df = _results_to_df(payload)
    with st.expander("전체 테이블 / CSV 다운로드"):
        st.dataframe(df, width="stretch")
        buffer = StringIO()
        df.to_csv(buffer, index=False)
        st.download_button(
            label="결과 CSV 다운로드",
            data=buffer.getvalue(),
            file_name=f"lowest-price-{query.strip()}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()

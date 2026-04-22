"""Streamlit 기반 내부 UI.

사용법: `streamlit run app/ui/streamlit_app.py`

백엔드 API(`/api/v1/search`)를 호출해 결과를 표로 표시하고 CSV 다운로드 기능을 제공한다.
"""

from __future__ import annotations

import os
from io import StringIO

import httpx
import pandas as pd
import streamlit as st

DEFAULT_API_BASE = os.getenv("LOWEST_PRICE_API_BASE", "http://localhost:8000")
PRIVATE_BANNER = (
    "⚠️ **비공개 친구용 도구** — 외부 공유 및 상용 목적 사용 금지. "
    "표시된 가격·배송비는 최종 플랫폼 페이지와 다를 수 있다."
)


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


def main() -> None:
    st.set_page_config(page_title="lowest-price", layout="wide")
    st.title("🛒 네이버·쿠팡 최저가 비교 (비공개)")
    st.warning(PRIVATE_BANNER)

    with st.sidebar:
        st.header("⚙️ 설정")
        api_base = st.text_input("API Base URL", value=DEFAULT_API_BASE)
        limit = st.slider("플랫폼당 수집 개수", 5, 40, 20, step=5)
        force_refresh = st.checkbox("캐시 무시", value=False)

    query = st.text_input("검색어", placeholder="예: 코카콜라 500ml")
    submit = st.button("검색", type="primary", disabled=not query.strip())

    if submit:
        with st.spinner("수집·파싱·정렬 중..."):
            try:
                payload = _fetch(api_base, query.strip(), limit, force_refresh)
            except httpx.HTTPError as exc:
                st.error(f"API 호출 실패: {exc}")
                return
        st.success(f"완료 — {len(payload.get('results', []))}개 옵션 (cached={payload.get('cached')})")
        sources = payload.get("sources", {})
        col1, col2, col3 = st.columns(3)
        col1.metric("Naver", sources.get("naver"))
        col2.metric("Coupang", sources.get("coupang"))
        col3.metric("Comparable", payload.get("comparable_group"))

        df = _results_to_df(payload)
        if df.empty:
            st.info("결과가 없습니다. 검색어를 바꿔보거나 캐시 무시를 시도해주세요.")
            return

        st.dataframe(df, width="stretch")

        buffer = StringIO()
        df.to_csv(buffer, index=False)
        st.download_button(
            label="⬇️ 결과 CSV 다운로드",
            data=buffer.getvalue(),
            file_name=f"lowest-price-{query.strip()}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()

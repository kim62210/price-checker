"""검색 서비스 — Wave 3 재설계 대기 중.

TODO(wave3): tasks.md §5 참고
- 크롤링 오케스트레이션(`_collect_naver`, `_collect_coupang`, `_enrich_details`) 전부 제거됨
- 입력을 tenant_id + 업로드된 procurement_results 로 교체
- 파서·배송비·랭킹만 수행하도록 재작성
- 응답 캐시 키에 tenant_id 네임스페이스 포함 (search:{tenant_id}:{md5(query|limit)})
"""

from __future__ import annotations


async def run_search(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError(
        "search_service 는 Wave 3 재설계 대상입니다. tasks.md §5 를 참고하세요.",
    )


__all__ = ["run_search"]

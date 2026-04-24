"""네이버 응답을 canonical procurement result 후보로 정규화."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.parsers.regex_parser import ParseResult, parse_option_text
from app.parsers.unit_price import calculate_unit_price
from app.price_collection.client import NaverShoppingItem
from app.procurement.models import ProcurementOrder


@dataclass(slots=True)
class CanonicalCollectedResult:
    source: str
    source_method: str
    product_url: str
    seller_name: str | None
    listed_price: Decimal
    per_unit_price: Decimal | None
    shipping_fee: Decimal
    unit_count: int
    external_offer_id: str | None
    compare_eligible: bool
    parser_version: int
    raw_excerpt: dict[str, object]
    failure_code: str | None


def normalize_naver_item(
    *,
    order: ProcurementOrder,
    item: NaverShoppingItem,
    parser_version: int,
) -> CanonicalCollectedResult:
    listed_price = Decimal(str(item.listed_price)).quantize(Decimal("0.01"))
    parsed = parse_option_text(item.title)
    if listed_price <= Decimal("0"):
        return CanonicalCollectedResult(
            source="naver",
            source_method="naver_openapi",
            product_url=item.product_url,
            seller_name=item.mall_name,
            listed_price=listed_price,
            per_unit_price=None,
            shipping_fee=Decimal("0.00"),
            unit_count=1,
            external_offer_id=item.product_id,
            compare_eligible=False,
            parser_version=parser_version,
            raw_excerpt={"productId": item.product_id, "mallName": item.mall_name},
            failure_code="zero_price",
        )

    if parsed is None:
        return CanonicalCollectedResult(
            source="naver",
            source_method="naver_openapi",
            product_url=item.product_url,
            seller_name=item.mall_name,
            listed_price=listed_price,
            per_unit_price=None,
            shipping_fee=Decimal("0.00"),
            unit_count=1,
            external_offer_id=item.product_id,
            compare_eligible=False,
            parser_version=parser_version,
            raw_excerpt={"productId": item.product_id, "mallName": item.mall_name},
            failure_code="unit_unparsed",
    )

    per_unit_price = _compute_order_unit_price(order=order, item=item, parsed=parsed)
    return CanonicalCollectedResult(
        source="naver",
        source_method="naver_openapi",
        product_url=item.product_url,
        seller_name=item.mall_name,
        listed_price=listed_price,
        per_unit_price=per_unit_price,
        shipping_fee=Decimal("0.00"),
        unit_count=max(parsed.piece_count, 1),
        external_offer_id=item.product_id,
        compare_eligible=True,
        parser_version=parser_version,
        raw_excerpt={"productId": item.product_id, "mallName": item.mall_name},
        failure_code=None,
    )


def _compute_order_unit_price(
    *,
    order: ProcurementOrder,
    item: NaverShoppingItem,
    parsed: ParseResult,
) -> Decimal:
    listed_price = Decimal(str(item.listed_price))
    if order.unit == "개" and parsed.piece_count > 0:
        return (listed_price / Decimal(parsed.piece_count)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    unit_price = calculate_unit_price(item.listed_price, 0, parsed, shipping_confidence="known")
    return Decimal(str(unit_price.unit_price_display or 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

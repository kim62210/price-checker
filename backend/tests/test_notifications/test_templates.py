"""notification template 관리 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotificationPolicyError
from app.notifications.schemas import NotificationTemplateCreate, NotificationTemplateVersionCreate
from app.notifications.service import NotificationTemplateService, TemplateRenderError


@pytest.mark.asyncio
async def test_create_approved_alimtalk_template_version(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    service = NotificationTemplateService(db_session)

    template = await service.create_template(
        tenant_id=test_tenant_a.id,
        payload=NotificationTemplateCreate(template_code="procurement_result", name="조달 결과"),
    )
    version = await service.create_version(
        tenant_id=test_tenant_a.id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="kakao_alimtalk",
            purpose="transactional",
            provider_template_key="KA01",
            review_status="approved",
            body="{{shop_name}} {{product_name}} 최저가 {{best_price}}원",
            fallback_body="{{shop_name}} {{product_name}} {{best_price}}원",
            variables=["shop_name", "product_name", "best_price"],
        ),
    )

    assert version.version == 1
    assert version.channel == "kakao_alimtalk"
    assert version.review_status == "approved"


@pytest.mark.asyncio
async def test_template_version_preserves_previous_body(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    service = NotificationTemplateService(db_session)
    template = await service.create_template(
        tenant_id=test_tenant_a.id,
        payload=NotificationTemplateCreate(template_code="quote_ready", name="견적 완료"),
    )

    first = await service.create_version(
        tenant_id=test_tenant_a.id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="sms",
            purpose="transactional",
            body="첫 본문 {{name}}",
            variables=["name"],
        ),
    )
    second = await service.create_version(
        tenant_id=test_tenant_a.id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="sms",
            purpose="transactional",
            body="둘째 본문 {{name}}",
            variables=["name"],
        ),
    )

    assert first.version == 1
    assert first.body == "첫 본문 {{name}}"
    assert second.version == 2
    assert second.body == "둘째 본문 {{name}}"


@pytest.mark.asyncio
async def test_marketing_template_cannot_use_alimtalk(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    service = NotificationTemplateService(db_session)
    template = await service.create_template(
        tenant_id=test_tenant_a.id,
        payload=NotificationTemplateCreate(template_code="promo", name="프로모션"),
    )

    with pytest.raises(NotificationPolicyError):
        await service.create_version(
            tenant_id=test_tenant_a.id,
            template_id=template.id,
            payload=NotificationTemplateVersionCreate(
                channel="kakao_alimtalk",
                purpose="marketing",
                body="할인 안내 {{shop_name}}",
                variables=["shop_name"],
            ),
        )


@pytest.mark.asyncio
async def test_render_template_requires_all_variables(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    service = NotificationTemplateService(db_session)
    template = await service.create_template(
        tenant_id=test_tenant_a.id,
        payload=NotificationTemplateCreate(template_code="render_test", name="렌더 테스트"),
    )
    version = await service.create_version(
        tenant_id=test_tenant_a.id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="sms",
            purpose="transactional",
            body="{{shop_name}} {{product_name}}",
            fallback_body="{{shop_name}}",
            variables=["shop_name", "product_name"],
        ),
    )

    rendered = service.render_version(
        version,
        variables={"shop_name": "알파", "product_name": "우유"},
    )
    assert rendered.body == "알파 우유"
    assert rendered.fallback_body == "알파"

    with pytest.raises(TemplateRenderError):
        service.render_version(version, variables={"shop_name": "알파"})

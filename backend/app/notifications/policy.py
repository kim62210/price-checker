"""notification 채널/동의 정책."""

from __future__ import annotations

from app.core.exceptions import NotificationPolicyError


def normalize_phone_e164(phone: str) -> str:
    """한국 휴대폰 번호를 E.164 형태로 정규화한다."""

    stripped = phone.strip()
    if stripped.startswith("+"):
        digits = "+" + "".join(ch for ch in stripped[1:] if ch.isdigit())
        if digits.startswith("+82") and len(digits) >= 12:
            return digits
        raise NotificationPolicyError("invalid_phone_number")

    digits_only = "".join(ch for ch in stripped if ch.isdigit())
    if digits_only.startswith("82") and len(digits_only) >= 11:
        return f"+{digits_only}"
    if digits_only.startswith("0") and len(digits_only) >= 10:
        return f"+82{digits_only[1:]}"
    raise NotificationPolicyError("invalid_phone_number")

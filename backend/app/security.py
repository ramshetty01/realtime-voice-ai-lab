"""Single-owner access controls; this is not multi-tenant account authorization."""

import hmac
import ipaddress
import os


def allowed_origins() -> list[str]:
    origins = [
        value.strip()
        for value in os.getenv(
            "CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
        ).split(",")
        if value.strip()
    ]
    if not origins or "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS must include exact trusted origins, not a wildcard."
        )
    return origins


def origin_allowed(origin: str | None) -> bool:
    return origin is None or origin in allowed_origins()


def authorized(host: str | None, token: str, authority: str | None = None) -> bool:
    expected = os.getenv("VOICE_API_TOKEN", "")
    if expected:
        return hmac.compare_digest(token.encode(), expected.encode())
    if os.getenv("VOICE_LOCAL_ONLY", "true").lower() != "true":
        return False
    if (authority or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False

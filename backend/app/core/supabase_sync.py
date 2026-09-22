import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return settings.SUPABASE_URL.rstrip("/")


def _enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> dict[str, str]:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def sync_supabase_user(email: str, password: str, full_name: str | None = None) -> None:
    """Create (or update) a GoTrue user via the Admin API so Supabase Auth can sign them in."""
    if not _enabled() or not email or not password:
        return
    body = {
        "email": email.strip().lower(),
        "password": password,
        "email_confirm": True,
        "role": "authenticated",
        "aud": "authenticated",
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {"full_name": full_name or ""},
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            existing = _find_user(client, email)
            if existing is not None:
                client.patch(f"{_base_url()}/auth/v1/admin/users/{existing['id']}", json=body, headers=_headers()).raise_for_status()
            else:
                client.post(f"{_base_url()}/auth/v1/admin/users", json=body, headers=_headers()).raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Supabase Auth sync failed for %s (status %s): core login unaffected", email, exc.response.status_code)
    except httpx.HTTPError as exc:
        logger.warning("Supabase Auth sync failed for %s: core login unaffected", email)


def sync_supabase_password(email: str, new_password: str) -> None:
    """Rotate the GoTrue password for an existing user to match the app-side password."""
    if not _enabled() or not email or not new_password:
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            existing = _find_user(client, email)
            if existing is None:
                return
            client.put(
                f"{_base_url()}/auth/v1/admin/users/{existing['id']}",
                json={"password": new_password},
                headers=_headers(),
            ).raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Supabase Auth password sync failed for %s (status %s)", email, exc.response.status_code)
    except httpx.HTTPError:
        logger.warning("Supabase Auth password sync failed for %s", email)


def _find_user(client: httpx.Client, email: str) -> dict | None:
    page = 1
    while True:
        resp = client.get(
            f"{_base_url()}/auth/v1/admin/users",
            params={"page": page, "per_page": 100},
            headers=_headers(),
        )
        resp.raise_for_status()
        users = resp.json().get("users") or []
        for usr in users:
            if usr.get("email", "").lower() == email.strip().lower():
                return usr
        if len(users) < 100:
            return None
        page += 1
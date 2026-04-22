"""WordPress REST API client.

Base URL : https://blog.webhostmost.com/wp-json/wp/v2
Auth     : Application Password — Basic base64(username:app_password)
           Generate in WP Admin → Users → Profile → Application Passwords
"""
from __future__ import annotations

import base64


def _headers(username: str, app_password: str) -> dict:
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _base(wp_url: str) -> str:
    return wp_url.rstrip("/") + "/wp-json/wp/v2"


# ── Posts ─────────────────────────────────────────────────────────────────────

async def create_post(
    ctx,
    wp_url: str,
    username: str,
    app_password: str,
    title: str,
    content: str,
    status: str = "draft",
    author_id: int = 3,
    categories: list[int] | None = None,
    tags: list[int] | None = None,
) -> dict:
    """Create a new WordPress post. Returns the created post object."""
    payload: dict = {
        "title": title,
        "content": content,
        "status": status,
        "author": author_id,
    }
    if categories:
        payload["categories"] = categories
    if tags:
        payload["tags"] = tags

    resp = await ctx.http.post(
        f"{_base(wp_url)}/posts",
        headers=_headers(username, app_password),
        json=payload,
    )
    return _parse_post(resp)


async def update_post(
    ctx,
    wp_url: str,
    username: str,
    app_password: str,
    post_id: int,
    **fields,
) -> dict:
    """Update an existing WP post (title, content, status, etc.)."""
    resp = await ctx.http.patch(
        f"{_base(wp_url)}/posts/{post_id}",
        headers=_headers(username, app_password),
        json={k: v for k, v in fields.items() if v is not None},
    )
    return _parse_post(resp)


async def list_posts(
    ctx,
    wp_url: str,
    username: str,
    app_password: str,
    per_page: int = 10,
    status: str = "draft,publish",
) -> list[dict]:
    """List recent posts."""
    resp = await ctx.http.get(
        f"{_base(wp_url)}/posts",
        headers=_headers(username, app_password),
        params={"per_page": per_page, "status": status, "orderby": "date", "order": "desc"},
    )
    if isinstance(resp, list):
        return [_parse_post(p) for p in resp]
    return []


async def verify_connection(
    ctx,
    wp_url: str,
    username: str,
    app_password: str,
) -> bool:
    """Verify WP credentials by requesting the current user endpoint."""
    try:
        resp = await ctx.http.get(
            f"{_base(wp_url)}/users/me",
            headers=_headers(username, app_password),
        )
        return isinstance(resp, dict) and bool(resp.get("id"))
    except Exception:
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_post(resp) -> dict:
    if not isinstance(resp, dict):
        return {}
    title = resp.get("title", {})
    content = resp.get("content", {})
    return {
        "id": resp.get("id"),
        "status": resp.get("status"),
        "title": title.get("rendered", title) if isinstance(title, dict) else title,
        "link": resp.get("link", ""),
        "date": resp.get("date", ""),
    }

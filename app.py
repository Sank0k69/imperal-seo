"""WP Blogger extension — core init, settings, store helpers."""
from __future__ import annotations

from imperal_sdk import Extension, ChatExtension
from params import UIStateModel

ext = Extension(
    "wp-blogger",
    version="1.3.0",
    display_name="WP Blogger",
    description="AI-powered WordPress content studio: keyword research, SE Rankings tracking, AI article writing with SEO optimization, and one-click publishing to WordPress.",
    icon="icon.svg",
    actions_explicit=True,
)

chat = ChatExtension(
    ext,
    tool_name="wp_blogger",
    description=(
        "WP Blogger. Keyword research, rankings tracking, "
        "content plan, AI article writing, publish to WordPress."
    ),
    max_rounds=10,
)


@ext.cache_model("ui_state")
class _UIStateCache(UIStateModel):
    pass

SETTINGS_COL = "seo_settings"
CONTENT_COL = "seo_content"
UI_STATE_COL = "seo_ui_state"

DEFAULT_SETTINGS: dict = {
    # SE Ranking
    "seranking_data_key": "",
    "seranking_project_key": "",
    "seranking_project_id": "",
    "seranking_domain": "",
    "seranking_source": "us",
    # WordPress
    "wp_url": "",
    "wp_username": "",
    "wp_app_password": "",
    "wp_author_id": 1,
    # Brand identity — used in newsletter generation
    "company_name": "",
    "brand_description": "",
    "brand_voice": "Direct and smart. Short punchy sentences. Bold without being arrogant. No corporate fluff.",
    "newsletter_cta": "Learn more",
    "site_url": "",
    "blog_url": "",
    "tg_url": "",
    "community_url": "",
}

DEFAULT_UI_STATE: dict = {
    "active_view": "plan",
    "selected_id": None,
    "editor_mode": "edit",  # "edit" | "preview"
    "kw_results": [],
    "rankings_results": [],
}


# ── Settings ──────────────────────────────────────────────────────────────────

async def load_settings(ctx) -> dict:
    try:
        page = await ctx.store.query(SETTINGS_COL, limit=1)
    except Exception:
        return dict(DEFAULT_SETTINGS)
    docs = getattr(page, "data", None) or []
    if docs and isinstance(getattr(docs[0], "data", None), dict):
        return {**DEFAULT_SETTINGS, **docs[0].data}
    return dict(DEFAULT_SETTINGS)


async def save_settings(ctx, values: dict) -> dict:
    current = await load_settings(ctx)
    merged = {**current, **{k: v for k, v in values.items() if v is not None and v != ""}}
    page = await ctx.store.query(SETTINGS_COL, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(SETTINGS_COL, docs[0].id, merged)
    else:
        await ctx.store.create(SETTINGS_COL, merged)
    return merged


# ── UI state ──────────────────────────────────────────────────────────────────

async def load_ui_state(ctx) -> dict:
    if getattr(ctx, "_cache", None) is not None:
        try:
            cached = await ctx.cache.get("ui_state", _UIStateCache)
            if cached is not None:
                return cached.model_dump()
        except Exception:
            pass
    try:
        page = await ctx.store.query(UI_STATE_COL, limit=1)
        docs = getattr(page, "data", None) or []
        if docs and isinstance(getattr(docs[0], "data", None), dict):
            return {**DEFAULT_UI_STATE, **docs[0].data}
    except Exception:
        pass
    return dict(DEFAULT_UI_STATE)


async def save_ui_state(ctx, values: dict) -> dict:
    current = await load_ui_state(ctx)
    merged = {**current, **{k: v for k, v in values.items() if v is not None}}
    if getattr(ctx, "_cache", None) is not None:
        try:
            await ctx.cache.set("ui_state", _UIStateCache(**merged), ttl_seconds=300)
            return merged
        except Exception:
            pass
    page = await ctx.store.query(UI_STATE_COL, limit=1)
    docs = getattr(page, "data", None) or []
    if docs:
        await ctx.store.update(UI_STATE_COL, docs[0].id, merged)
    else:
        await ctx.store.create(UI_STATE_COL, merged)
    return merged


# ── Content store ─────────────────────────────────────────────────────────────

async def list_content(ctx, status: str | None = None) -> list[dict]:
    try:
        page = await ctx.store.query(CONTENT_COL, limit=100)
    except Exception:
        return []
    docs = getattr(page, "data", None) or []
    items = [d.data for d in docs if isinstance(getattr(d, "data", None), dict)]
    # attach store id to each item
    for d, item in zip(docs, items):
        item["id"] = d.id
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


async def get_content(ctx, content_id: str) -> dict | None:
    try:
        doc = await ctx.store.get(CONTENT_COL, content_id)
        if doc and isinstance(getattr(doc, "data", None), dict):
            result = dict(doc.data)
            result["id"] = doc.id
            return result
    except Exception:
        pass
    return None


async def create_content(ctx, data: dict) -> str:
    doc = await ctx.store.create(CONTENT_COL, data)
    return doc.id


async def update_content(ctx, content_id: str, data: dict) -> None:
    try:
        doc = await ctx.store.get(CONTENT_COL, content_id)
        if doc and isinstance(getattr(doc, "data", None), dict):
            merged = {**doc.data, **data}
            await ctx.store.update(CONTENT_COL, content_id, merged)
            return
    except Exception:
        pass
    await ctx.store.update(CONTENT_COL, content_id, data)


async def delete_content(ctx, content_id: str) -> None:
    await ctx.store.delete(CONTENT_COL, content_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

@ext.health_check
async def health_check(ctx):
    """Verify extension is alive; returns degraded if no APIs are configured."""
    s = await load_settings(ctx)
    if not ser_ready(s) and not wp_ready(s):
        return {"status": "degraded", "reason": "No API keys configured — open Settings."}
    return {"status": "ok"}


def ser_ready(s: dict) -> bool:
    return bool(s.get("seranking_data_key"))

def wp_ready(s: dict) -> bool:
    return bool(s.get("wp_app_password"))

"""MOS server HTTP client — all external API calls go through here."""
from __future__ import annotations

import time

from app import load_settings

SERVER_URL = "https://mos.lexa-lox.xyz"
SERVER_API_KEY = "dd5f08814b30d05ff8b573231a14a6826c39d7c07f226995c9a8b1573ceebb90"
TIMEOUT = 30
TIMEOUT_PLAN = 120  # content plan: 3 parallel API calls + AI generation


async def log_action(ctx, action: str, content_id: str, duration_ms: int,
                     success: bool, error: str = "") -> None:
    """Fire-and-forget: POST action log to MOS. Never raises."""
    try:
        await ctx.http.post(
            f"{SERVER_URL}/api/logs/action",
            json={
                "action": action,
                "content_id": content_id or "",
                "duration_ms": duration_ms,
                "success": success,
                "error": error,
                "timestamp": time.time(),
            },
            headers={"X-API-Key": SERVER_API_KEY},
            timeout=5,
        )
    except Exception:
        pass  # logging must never break the action


async def _post(ctx, endpoint: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    resp = await ctx.http.post(
        f"{SERVER_URL}{endpoint}",
        json=payload,
        headers={"X-API-Key": SERVER_API_KEY},
        timeout=timeout,
    )
    if not resp.ok:
        return {"error": f"Server error {resp.status_code}"}
    return resp.json()


async def _get(ctx, endpoint: str, timeout: int = TIMEOUT) -> dict:
    resp = await ctx.http.get(
        f"{SERVER_URL}{endpoint}",
        headers={"X-API-Key": SERVER_API_KEY},
        timeout=timeout,
    )
    if not resp.ok:
        return {"error": f"Server error {resp.status_code}"}
    return resp.json()


async def ser_keywords(ctx, domain: str, source: str, limit: int, min_volume: int, max_difficulty: int) -> dict:
    s = await load_settings(ctx)
    key = s.get("seranking_data_key", "")
    if not key:
        return {"error": "SE Ranking Data API key not configured. Go to Settings."}
    return await _post(ctx, "/api/seranking/keywords", {
        "seranking_data_key": key,
        "domain": domain,
        "source": source,
        "limit": limit,
        "min_volume": min_volume,
        "max_difficulty": max_difficulty,
    })


async def ser_gaps(ctx, domain: str, competitor: str, source: str, limit: int) -> dict:
    s = await load_settings(ctx)
    key = s.get("seranking_data_key", "")
    if not key:
        return {"error": "SE Ranking Data API key not configured. Go to Settings."}
    return await _post(ctx, "/api/seranking/gaps", {
        "seranking_data_key": key,
        "domain": domain,
        "competitor": competitor,
        "source": source,
        "limit": limit,
    })


async def ser_rankings(ctx) -> dict:
    s = await load_settings(ctx)
    key = s.get("seranking_project_key", "")
    project_id = s.get("seranking_project_id", "")
    if not key:
        return {"error": "SE Ranking Project API key not configured. Go to Settings."}
    if not project_id:
        return {"error": "SE Ranking Project ID not configured. Go to Settings."}
    return await _post(ctx, "/api/seranking/rankings", {
        "seranking_project_key": key,
        "project_id": project_id,
    })


async def ser_projects(ctx) -> dict:
    s = await load_settings(ctx)
    key = s.get("seranking_project_key", "")
    if not key:
        return {"error": "SE Ranking Project API key not configured. Go to Settings."}
    return await _post(ctx, "/api/seranking/projects", {
        "seranking_project_key": key,
    })


async def content_plan(ctx, competitor: str = "", language: str = "en",
                       existing_keywords: list = None) -> dict:
    s = await load_settings(ctx)

    # Try imperal-analytics IPC first; fall back to own Matomo credentials
    growing_pages = []
    matomo_url = matomo_token = ""
    matomo_site_id = 1
    try:
        result = await ctx.extensions.call("analytics", "growing_pages", limit=20)
        if result and not getattr(result, "error", None):
            data = getattr(result, "data", {}) or {}
            growing_pages = data.get("pages", [])
    except Exception:
        pass

    if not growing_pages:
        matomo_url    = s.get("matomo_url", "")
        matomo_token  = s.get("matomo_token", "")
        matomo_site_id = s.get("matomo_site_id", 1)

    return await _post(ctx, "/api/content/plan", {
        "user_key":      "",
        "seranking_key": s.get("seranking_data_key", ""),
        "domain":        s.get("seranking_domain", ""),
        "source":        s.get("seranking_source", "us"),
        "competitor":    competitor or s.get("seranking_competitor", ""),
        "language":      language,
        "profile_name":  s.get("active_profile", ""),
        "wp_url":        s.get("wp_url", ""),
        "wp_user":       s.get("wp_username", ""),
        "wp_password":   s.get("wp_app_password", ""),
        # Matomo — used only if analytics extension not installed
        "matomo_url":    matomo_url,
        "matomo_token":  matomo_token,
        "matomo_site_id": matomo_site_id,
        # Pre-fetched from analytics IPC (skips Matomo fetch on server)
        "growing_pages": growing_pages,
        # Existing keywords from extension store (avoid duplicates in plan + WP)
        "existing_plan_keywords": existing_keywords or [],
    }, timeout=TIMEOUT_PLAN)


async def generate_brief(ctx, keyword: str, content_type: str = "blog",
                         volume: int = 0, difficulty: int = 0,
                         extra: str = "", language: str = "en") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/brief", {
        "keyword":      keyword,
        "content_type": content_type,
        "volume":       volume,
        "difficulty":   difficulty,
        "extra":        extra,
        "language":     language,
    }, timeout=25)


async def generate_newsletter_mos(ctx, news_text: str, tone_note: str = "") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/newsletter", {
        "news_text":         news_text,
        "tone_note":         tone_note,
        "company_name":      s.get("company_name", ""),
        "brand_description": s.get("brand_description", ""),
        "brand_voice":       s.get("brand_voice", ""),
        "newsletter_cta":    s.get("newsletter_cta", ""),
        "site_url":          s.get("site_url", ""),
        "blog_url":          s.get("blog_url", ""),
        "tg_url":            s.get("tg_url", ""),
        "language":          s.get("language", "en"),
    }, timeout=60)


async def keywords_for_article(ctx, keyword: str) -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/keywords_for_article", {
        "seranking_key": s.get("seranking_data_key", ""),
        "domain":        s.get("seranking_domain", ""),
        "keyword":       keyword,
        "language":      s.get("language", "en"),
    }, timeout=60)


def _article_payload(s: dict, topic: str, keyword: str, article_type: str,
                     word_count: int, language: str, secondary_keywords: list,
                     lsi_terms: list, questions: list,
                     brand_context: str, ser_context: str) -> dict:
    return {
        "user_key":           "",
        "topic":              topic,
        "keyword":            keyword,
        "language":           language,
        "word_count":         word_count,
        "article_type":       article_type,
        "secondary_keywords": secondary_keywords or [],
        "lsi_terms":          lsi_terms or [],
        "questions":          questions or [],
        "brand_voice":        s.get("brand_voice", ""),
        "company_name":       s.get("company_name", ""),
        "brand_description":  s.get("brand_description", ""),
        "site_url":           s.get("site_url", ""),
        "blog_url":           s.get("blog_url", ""),
        "brand_context":      brand_context,
        "ser_context":        ser_context,
    }


async def generate_article(ctx, topic: str, keyword: str, article_type: str = "blog",
                            word_count: int = 1500, language: str = "en",
                            secondary_keywords: list = None, lsi_terms: list = None,
                            questions: list = None,
                            brand_context: str = "", ser_context: str = "") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/generate",
                       _article_payload(s, topic, keyword, article_type, word_count, language,
                                        secondary_keywords, lsi_terms, questions,
                                        brand_context, ser_context),
                       timeout=120)


async def start_generate_article(ctx, topic: str, keyword: str, article_type: str = "blog",
                                  word_count: int = 1500, language: str = "en",
                                  secondary_keywords: list = None, lsi_terms: list = None,
                                  questions: list = None,
                                  brand_context: str = "", ser_context: str = "") -> dict:
    """Start background article generation. Returns {job_id, status: 'pending'} immediately."""
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/generate/start",
                       _article_payload(s, topic, keyword, article_type, word_count, language,
                                        secondary_keywords, lsi_terms, questions,
                                        brand_context, ser_context),
                       timeout=10)


async def poll_article_job(ctx, job_id: str) -> dict:
    """Poll job status. Returns {status: pending|done|error|not_found, result?: {...}}"""
    return await _get(ctx, f"/api/content/jobs/{job_id}", timeout=10)


async def start_refine_article(ctx, content: str, keyword: str, instruction: str = "") -> dict:
    """Start background article improvement. Returns {job_id, status: 'pending'} immediately."""
    return await _post(ctx, "/api/content/refine/start", {
        "user_key":    "",
        "content":     content,
        "keyword":     keyword,
        "instruction": instruction,
    }, timeout=10)


async def wp_publish(ctx, title: str, content: str, status: str = "draft") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/wordpress/publish", {
        "wp_url": s.get("wp_url", ""),
        "wp_user": s.get("wp_username", ""),
        "wp_password": s.get("wp_app_password", ""),
        "title": title,
        "content": content,
        "status": status,
    })


async def wp_update(ctx, post_id: int, title: str = "", content: str = "", status: str = "") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/wordpress/update", {
        "wp_url": s.get("wp_url", ""),
        "wp_user": s.get("wp_username", ""),
        "wp_password": s.get("wp_app_password", ""),
        "post_id": post_id,
        "title": title,
        "content": content,
        "status": status,
    })


# ── MOS Storage — user-isolated content + docs ────────────────────────────────

def _scope(ctx) -> dict:
    """User context for storage isolation — (tenant_id, user_id) composite key."""
    return {
        "user_id": ctx.user.imperal_id,
        "tenant_id": ctx.user.tenant_id,
    }


async def mos_content_list(ctx) -> list:
    data = await _post(ctx, "/api/storage/content/list", _scope(ctx))
    return data.get("items", [])


async def mos_content_get(ctx, item_id: str) -> dict:
    return await _post(ctx, "/api/storage/content/get", {**_scope(ctx), "id": item_id})


async def mos_content_create(ctx, item: dict) -> dict:
    return await _post(ctx, "/api/storage/content/create", {**_scope(ctx), **item})


async def mos_content_update(ctx, item_id: str, fields: dict) -> dict:
    return await _post(ctx, "/api/storage/content/update", {**_scope(ctx), "id": item_id, **fields})


async def mos_content_delete(ctx, item_id: str) -> dict:
    return await _post(ctx, "/api/storage/content/delete", {**_scope(ctx), "id": item_id})


async def mos_docs_list(ctx) -> list:
    data = await _post(ctx, "/api/storage/docs/list", _scope(ctx))
    return data.get("docs", [])


async def mos_docs_get_all(ctx) -> list:
    """Returns docs with full content — for AI context injection."""
    data = await _post(ctx, "/api/storage/docs/get_all", _scope(ctx))
    return data.get("docs", [])


async def mos_docs_create(ctx, name: str, content: str, size: int = 0, ext: str = "md") -> dict:
    return await _post(ctx, "/api/storage/docs/create", {
        **_scope(ctx), "name": name, "content": content, "size": size, "ext": ext,
    })


async def mos_docs_delete(ctx, doc_id: str) -> dict:
    return await _post(ctx, "/api/storage/docs/delete", {**_scope(ctx), "id": doc_id})

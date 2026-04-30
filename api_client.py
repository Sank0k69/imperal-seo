"""MOS server HTTP client — all external API calls go through here."""
from __future__ import annotations

from app import load_settings

SERVER_URL = "https://mos.lexa-lox.xyz"
SERVER_API_KEY = "dd5f08814b30d05ff8b573231a14a6826c39d7c07f226995c9a8b1573ceebb90"
TIMEOUT = 30
TIMEOUT_PLAN = 120  # content plan: 3 parallel API calls + AI generation


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


async def content_plan(ctx, competitor: str = "", language: str = "en") -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/plan", {
        "user_key":     "",
        "seranking_key": s.get("seranking_data_key", ""),
        "domain":        s.get("seranking_domain", ""),
        "source":        s.get("seranking_source", "us"),
        "competitor":    competitor or s.get("seranking_competitor", ""),
        "language":      language,
        "profile_name":  "",
        "wp_url":        s.get("wp_url", ""),
        "wp_user":       s.get("wp_username", ""),
        "wp_password":   s.get("wp_app_password", ""),
        # Matomo — blog growth data
        "matomo_url":      s.get("matomo_url", ""),
        "matomo_token":    s.get("matomo_token", ""),
        "matomo_site_id":  s.get("matomo_site_id", 1),
    }, timeout=TIMEOUT_PLAN)


async def keywords_for_article(ctx, keyword: str) -> dict:
    s = await load_settings(ctx)
    return await _post(ctx, "/api/content/keywords_for_article", {
        "seranking_key": s.get("seranking_data_key", ""),
        "domain":        s.get("seranking_domain", ""),
        "keyword":       keyword,
        "language":      s.get("language", "en"),
    }, timeout=60)


async def generate_article(ctx, topic: str, keyword: str, article_type: str = "blog",
                            word_count: int = 1500, language: str = "en",
                            secondary_keywords: list = None, lsi_terms: list = None,
                            questions: list = None) -> dict:
    return await _post(ctx, "/api/content/generate", {
        "user_key":           "",
        "topic":              topic,
        "keyword":            keyword,
        "language":           language,
        "word_count":         word_count,
        "article_type":       article_type,
        "secondary_keywords": secondary_keywords or [],
        "lsi_terms":          lsi_terms or [],
        "questions":          questions or [],
    }, timeout=120)


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

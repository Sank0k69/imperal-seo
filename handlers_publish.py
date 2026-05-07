"""Publishing handlers — WordPress publish + SEO meta setup."""
import re
import time

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, load_settings, load_ui_state, list_content
from app import save_settings as _save_settings
from api_client import log_action, _post
from api_wordpress import create_post, update_post
from params import PublishWpParams, SaveSettingsParams, SetWpSeoParams


async def _resolve_id(ctx, content_id: str, keyword_hint: str = "") -> str:
    """Resolve content_id: explicit → UI state selected_id → search by keyword → most recent.

    All logic on the server — Webbee just passes what the user said.
    """
    if content_id:
        return content_id
    state = await load_ui_state(ctx)
    if state.get("selected_id"):
        return state["selected_id"]
    if keyword_hint:
        items = await list_content(ctx)
        q = keyword_hint.lower()
        for item in items:
            kw    = (item.get("keyword") or "").lower()
            title = (item.get("title") or "").lower()
            if q in kw or q in title:
                return item["id"]
        # partial word match
        for word in q.split():
            for item in items:
                kw    = (item.get("keyword") or "").lower()
                title = (item.get("title") or "").lower()
                if word in kw or word in title:
                    return item["id"]
    return ""


async def _auto_seo(ctx, cid: str, wp_post_id: int, item: dict, s: dict) -> None:
    """Auto-generate and set Rank Math SEO fields after publish. Runs on MOS VPS."""
    try:
        title   = item.get("title") or item.get("keyword", "")
        keyword = item.get("focus_keyword") or item.get("keyword", "")
        content = item.get("content", "")
        language = s.get("language", "en")

        # Use stored meta if available, else generate via MOS
        meta_desc = item.get("meta_description", "")
        excerpt   = item.get("excerpt", "")
        if not meta_desc or not excerpt:
            seo = await _post(ctx, "/api/content/seo_meta", {
                "title":            title,
                "keyword":          keyword,
                "content_snippet":  content[:500],
                "language":         language,
            })
            if "error" not in seo:
                meta_desc = meta_desc or seo.get("meta_description", "")
                excerpt   = excerpt   or seo.get("excerpt", "")

        # Rank Math focus keyword: primary + up to 4 secondary
        secondary  = item.get("secondary_keywords", [])
        all_kws    = [keyword] + [k for k in secondary[:4] if k.lower() != keyword.lower()]
        rm_focus   = ", ".join(filter(None, all_kws))

        await update_post(
            ctx, s["wp_url"], s["wp_username"], s["wp_app_password"],
            post_id=wp_post_id,
            excerpt=excerpt,
            meta={
                "rank_math_focus_keyword": rm_focus,
                "rank_math_description":   meta_desc,
            },
        )
        await update_content(ctx, cid, {
            "meta_description": meta_desc,
            "focus_keyword":    keyword,
            "excerpt":          excerpt,
        })
    except Exception:
        pass  # SEO update is best-effort, never block publish

# ── Category IDs (blog.webhostmost.com) ───────────────────────────────────────
_KW_CATEGORIES = {
    "wordpress": 46,
    "webhostmost": 47,
    "wpanel": 47,
    "webbee": 47,
    "imperal": 47,
}
_TYPE_CATEGORIES = {
    "comparison": 21,
    "review": 21,
    "news": 51,
    "tutorial": 45,
    "blog": 45,
    "pillar": 48,
}


def _pick_category(keyword: str, article_type: str) -> int:
    kw_lower = keyword.lower()
    for kw, cat_id in _KW_CATEGORIES.items():
        if kw in kw_lower:
            return cat_id
    return _TYPE_CATEGORIES.get(article_type, 45)


def _prepare_content(content: str, faq_schema: str, blog_url: str) -> str:
    """Resolve [INTERNAL] placeholders, strip em/en dashes, append FAQ JSON-LD."""
    if blog_url:
        content = re.sub(r'href="\[INTERNAL\]"', f'href="{blog_url.rstrip("/")}"', content)
    else:
        content = re.sub(r'href="\[INTERNAL\]"', 'href="#"', content)
    # Brand rule: no em dash (—) or en dash (–) — replace with space-hyphen-space
    content = re.sub(r'\s*[—–]\s*', ' - ', content)
    if faq_schema:
        content = content + "\n" + faq_schema
    return content


@chat.function(
    "publish_wp",
    description="Create or update a WordPress post from a blog content item. status: 'draft' or 'publish'.",
    action_type="write",
    chain_callable=True,
    effects=["publish:post"],
    event="seo.content.published",
)
async def publish_wp(ctx, params: PublishWpParams) -> ActionResult:
    """Create or update a WordPress post as draft or published."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id, params.keyword_hint)
    action_name = f"publish_wp_{params.status}"
    try:
        s = await load_settings(ctx)
        if not s.get("wp_app_password"):
            await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), False, "WP not configured")
            return ActionResult.error(error=(
                "WordPress Application Password not configured. "
                "Go to Settings → WordPress → Application Passwords."
            ))

        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")

        title      = item.get("title") or item.get("keyword", "Untitled")
        raw_content = item.get("content", "")
        if not raw_content:
            await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), False, "Content is empty")
            return ActionResult.error(error="Content is empty — run AI Write first.")

        wp_post_id   = item.get("wp_post_id")
        wp_url       = s["wp_url"]
        username     = s["wp_username"]
        app_pw       = s["wp_app_password"]
        author_id    = int(s.get("wp_author_id", 3))
        blog_url     = s.get("blog_url", "")
        faq_schema   = item.get("faq_schema", "")
        article_type = item.get("type", "blog")
        keyword      = item.get("keyword", "")
        category_id  = _pick_category(keyword, article_type)
        content      = _prepare_content(raw_content, faq_schema, blog_url)

        if wp_post_id:
            post = await update_post(
                ctx, wp_url, username, app_pw,
                post_id=int(wp_post_id),
                title=title, content=content, status=params.status,
                categories=[category_id],
            )
            wp_action = "updated"
        else:
            post = await create_post(
                ctx, wp_url, username, app_pw,
                title=title, content=content, status=params.status,
                author_id=author_id, categories=[category_id],
            )
            wp_action = "created"

        if not post.get("id"):
            wp_msg = post.get("_wp_error") or str(post)
            await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), False, f"WordPress error: {wp_msg[:200]}")
            return ActionResult.error(error=f"WordPress error: {wp_msg}")

        new_status = "published" if params.status == "publish" else item.get("status", "review")
        await update_content(ctx, cid, {
            "wp_post_id":  post["id"],
            "target_url":  post.get("link", ""),
            "status":      new_status,
            "wp_category": category_id,
        })

        # Auto-set Rank Math SEO fields (meta description, focus keyword, excerpt)
        await _auto_seo(ctx, cid, int(post["id"]), item, s)

        await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success(
            {"wp_id": post["id"], "link": post.get("link", ""), "wp_status": params.status},
            summary=f"Post {wp_action} on WordPress (ID {post['id']}, status: {params.status}). Rank Math SEO set. {post.get('link', '')}",
        )
    except Exception as e:
        await log_action(ctx, action_name, cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))


@chat.function(
    "publish_wp_draft",
    description="Publish or update the current WordPress post as a draft.",
    action_type="write",
    chain_callable=True,
    effects=["publish:post"],
    event="seo.content.published",
)
async def publish_wp_draft(ctx, params: PublishWpParams) -> ActionResult:
    """Publish or update the current post as a WordPress draft."""
    params.status = "draft"
    return await publish_wp(ctx, params)


@chat.function(
    "publish_wp_publish",
    description="Publish or update the current WordPress post as published (live).",
    action_type="write",
    chain_callable=True,
    effects=["publish:post"],
    event="seo.content.published",
)
async def publish_wp_publish(ctx, params: PublishWpParams) -> ActionResult:
    """Publish or update the current post as live on WordPress."""
    params.status = "publish"
    return await publish_wp(ctx, params)


@chat.function(
    "set_wp_seo",
    description=(
        "Set Rank Math SEO on the WordPress post: focus + secondary keywords, meta description, excerpt. "
        "Auto-generates meta description and excerpt if not provided. Call after publish_wp."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:post"],
    event="seo.content.updated",
)
async def set_wp_seo(ctx, params: SetWpSeoParams) -> ActionResult:
    """Set Rank Math SEO fields on the WordPress post."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id, params.keyword_hint)
    try:
        s = await load_settings(ctx)
        if not s.get("wp_app_password"):
            await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), False, "WordPress not configured")
            return ActionResult.error(error="WordPress not configured. Go to Settings.")

        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")

        wp_post_id = item.get("wp_post_id")
        if not wp_post_id:
            await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), False, "No wp_post_id")
            return ActionResult.error(error="Publish to WordPress first, then set SEO.")

        focus_kw       = params.focus_keyword or item.get("focus_keyword") or item.get("keyword", "")
        secondary_kws  = item.get("secondary_keywords", [])
        title          = item.get("title") or item.get("keyword", "")
        content_html   = item.get("content", "")

        # Rank Math focus keyword field: primary + up to 4 secondary (comma-separated)
        all_kws = [focus_kw] + [k for k in secondary_kws[:4] if k.lower() != focus_kw.lower()]
        rm_focus_kw = ", ".join(all_kws)

        # Meta description: provided → stored → generate
        meta_desc = params.meta_description or item.get("meta_description", "")
        if not meta_desc:
            result = await ctx.ai.complete(
                f"Write an SEO meta description.\n"
                f"Title: {title}\nFocus keyword: {focus_kw}\n\n"
                "Rules: 120-155 characters, include the focus keyword naturally, active voice, no quotes, no trailing period."
            )
            meta_desc = (getattr(result, "text", None) or str(result)).strip().strip('"').strip("'")[:155]

        # Excerpt: short plain-text teaser for WordPress blog listing
        excerpt_result = await ctx.ai.complete(
            f"Write a WordPress post excerpt.\n"
            f"Title: {title}\nFocus keyword: {focus_kw}\n"
            f"Article opening (first 400 chars): {content_html[:400]}\n\n"
            "Rules: 130-150 characters, plain text (no HTML), include the focus keyword, factual and compelling."
        )
        excerpt = (getattr(excerpt_result, "text", None) or str(excerpt_result)).strip().strip('"').strip("'")[:150]

        # Update WP: Rank Math meta fields + native excerpt
        post = await update_post(
            ctx,
            s["wp_url"], s["wp_username"], s["wp_app_password"],
            post_id=int(wp_post_id),
            excerpt=excerpt,
            meta={
                "rank_math_focus_keyword": rm_focus_kw,
                "rank_math_description":   meta_desc,
            },
        )

        if not post.get("id"):
            wp_msg = post.get("_wp_error") or str(post)
            await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), False, f"WP SEO update failed: {wp_msg[:200]}")
            return ActionResult.error(error=f"WP SEO update failed: {wp_msg}")

        await update_content(ctx, cid, {
            "meta_description": meta_desc,
            "focus_keyword":    focus_kw,
            "excerpt":          excerpt,
        })

        kw_count = len(all_kws)
        await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success(
            {"focus_keyword": focus_kw, "keywords_set": kw_count, "meta_description": meta_desc},
            summary=(
                f"Rank Math SEO set — {kw_count} keywords: {rm_focus_kw[:60]}\n"
                f"Meta: {meta_desc[:80]}...\n"
                f"Excerpt: {excerpt[:60]}..."
            ),
        )
    except Exception as e:
        await log_action(ctx, "set_wp_seo", cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))


@chat.function(
    "save_settings",
    description="Save API keys and configuration for SE Ranking and WordPress.",
    action_type="write",
    chain_callable=True,
    effects=["update:settings"],
    event="seo.settings.saved",
)
async def save_settings_fn(ctx, params: SaveSettingsParams) -> ActionResult:
    """Save extension settings (API keys, WP credentials)."""
    updated = await _save_settings(ctx, params.model_dump(exclude_none=True))
    keys_set = [k for k, v in updated.items() if v and (k.endswith("_key") or k.endswith("_password"))]
    return ActionResult.success(
        {"updated": list(updated.keys())},
        summary=f"Settings saved. Credentials configured: {', '.join(keys_set) or 'none'}",
    )

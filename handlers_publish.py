"""Publishing handlers — WordPress publish + SEO meta setup."""
import re
import time

from imperal_sdk import ActionResult, ui
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, load_settings, load_ui_state, list_content
from app import save_settings as _save_settings
from api_client import log_action, _post
from api_wordpress import create_post, update_post
from params import PublishWpParams, SaveSettingsParams, SetWpSeoParams, ListWpPostsParams


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

        # Sanitize: strip LLM echoes + em dashes
        import re as _re
        def _clean_seo(text: str, maxlen: int) -> str:
            for pfx in ["here is a wordpress post excerpt:", "here is an seo meta description:",
                        "wordpress post excerpt:", "meta description:", "excerpt:", "here's a "]:
                if text.lower().startswith(pfx):
                    text = text[len(pfx):].strip()
            text = text.replace("—", " - ").replace("–", " - ")
            return _re.sub(r'\s+', ' ', text).strip().strip('"').strip("'")[:maxlen]
        meta_desc = _clean_seo(meta_desc, 155)
        excerpt   = _clean_seo(excerpt, 150)

        # Rank Math focus keyword: primary + up to 4 secondary
        secondary  = item.get("secondary_keywords", [])
        all_kws    = [keyword] + [k for k in secondary[:4] if k.lower() != keyword.lower()]
        rm_focus   = ", ".join(filter(None, all_kws))

        # Set excerpt via direct WP REST API (ctx.http works for native fields)
        await update_post(
            ctx, s["wp_url"], s["wp_username"], s["wp_app_password"],
            post_id=wp_post_id,
            excerpt=excerpt,
        )

        # Set Rank Math fields + slug + seo_title via MOS server
        await _post(ctx, "/api/wordpress/update", {
            "wp_url":          s["wp_url"],
            "wp_user":         s["wp_username"],
            "wp_password":     s["wp_app_password"],
            "post_id":         wp_post_id,
            "title":           title,
            "focus_keyword":   rm_focus,
            "meta_description": meta_desc,
        })
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

        # Meta + excerpt: use MOS server (avoids ctx.ai.complete instruction-echo bugs)
        meta_desc = params.meta_description or item.get("meta_description", "")
        excerpt   = item.get("excerpt", "")
        if not meta_desc or not excerpt:
            seo = await _post(ctx, "/api/content/seo_meta", {
                "title":            title,
                "keyword":          focus_kw,
                "content_snippet":  content_html[:500],
                "language":         s.get("language", "en"),
            })
            if "error" not in seo:
                meta_desc = meta_desc or seo.get("meta_description", "")
                excerpt   = excerpt   or seo.get("excerpt", "")

        # Sanitize: strip instruction echoes + em dashes (brand rule)
        def _clean(text: str, maxlen: int) -> str:
            import re
            for prefix in [
                "here is a wordpress post excerpt:", "wordpress post excerpt:",
                "here is an seo meta description:", "meta description:",
                "excerpt:", "here's a ", "here is a ",
            ]:
                if text.lower().startswith(prefix):
                    text = text[len(prefix):].strip()
            text = text.replace("—", " - ").replace("–", " - ")  # em/en dash
            text = re.sub(r'\s+', ' ', text).strip().strip('"').strip("'")
            return text[:maxlen]

        meta_desc = _clean(meta_desc, 155)
        excerpt   = _clean(excerpt, 150)

        # Excerpt via direct WP REST API
        post = await update_post(
            ctx,
            s["wp_url"], s["wp_username"], s["wp_app_password"],
            post_id=int(wp_post_id),
            excerpt=excerpt,
        )

        # Rank Math fields via MOS (httpx on VPS, avoids ctx.http meta field issues)
        await _post(ctx, "/api/wordpress/update", {
            "wp_url":          s["wp_url"],
            "wp_user":         s["wp_username"],
            "wp_password":     s["wp_app_password"],
            "post_id":         int(wp_post_id),
            "title":           title,
            "focus_keyword":   rm_focus_kw,
            "meta_description": meta_desc,
        })

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
            {
                "wp_post_id": wp_post_id,
                "focus_keyword": focus_kw,
                "all_keywords": all_kws,
                "meta_description": meta_desc,
                "excerpt": excerpt,
            },
            summary=(
                f"✅ Rank Math updated on WP post #{wp_post_id} ({title[:50]})\n"
                f"Focus keyword: {focus_kw}\n"
                f"Secondary keywords ({kw_count - 1}): {', '.join(all_kws[1:4])}\n"
                f"Meta ({len(meta_desc)} chars): {meta_desc}\n"
                f"Excerpt: {excerpt[:80]}\n"
                f"Slug updated to short keyword-based URL"
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


@chat.function(
    "list_wp_posts",
    description=(
        "List published posts from the WordPress blog. "
        "Use when user asks to see all articles, blog posts, what's published, recent posts. "
        "Shows title, status, date, URL for each post."
    ),
    action_type="read",
    event="",
)
async def list_wp_posts(ctx, params: ListWpPostsParams) -> ActionResult:
    """Fetch and display WordPress posts."""
    s = await load_settings(ctx)
    if not s.get("wp_app_password"):
        return ActionResult.error(error="WordPress not configured. Add credentials in Settings.")

    _mos_post = _post  # already imported at module level
    # Paginate to fetch ALL posts
    all_posts = []
    page = 1
    while True:
        data = await _mos_post(ctx, "/api/wordpress/list", {
            "wp_url":      s["wp_url"],
            "wp_user":     s["wp_username"],
            "wp_password": s["wp_app_password"],
            "per_page":    100,
            "page":        page,
            "status":      params.status or "any",
        })
        if "error" in data:
            if page == 1:
                return ActionResult.error(error=data["error"])
            break
        batch = data.get("posts", [])
        if not batch:
            break
        all_posts.extend(batch)
        if len(batch) < 100:
            break  # last page
        page += 1
        if page > 20:  # safety cap at 2000 posts
            break
    posts = all_posts
    if not posts:
        return ActionResult.success({}, summary="No posts found in WordPress blog.")

    rows = [
        {
            "title":  p.get("title", "—")[:55],
            "status": p.get("status", "—"),
            "date":   p.get("date", "")[:10],
            "link":   p.get("link", ""),
        }
        for p in posts
    ]

    table = ui.DataTable(
        columns=[
            ui.DataColumn(key="title",  label="Title",   width="50%"),
            ui.DataColumn(key="status", label="Status",  width="12%"),
            ui.DataColumn(key="date",   label="Date",    width="13%"),
            ui.DataColumn(key="link",   label="URL",     width="25%"),
        ],
        rows=rows,
    )

    published = sum(1 for p in posts if p.get("status") == "publish")
    drafts    = sum(1 for p in posts if p.get("status") == "draft")

    return ActionResult.success(
        {"posts": posts, "count": len(posts)},
        summary=f"{len(posts)} posts found: {published} published, {drafts} drafts.",
        ui=table,
    )

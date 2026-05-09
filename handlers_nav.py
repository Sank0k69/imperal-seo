"""Navigation handlers + content creation."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from wpb_app import chat, save_ui_state, create_content as _create, get_content as _get_content
from params import OpenEditorParams, CreateContentParams, SetEditorModeParams, EmptyParams, ImportFromWpParams


@chat.function("go_plan", description="Switch main panel to Content Plan view.", action_type="read", event="seo.nav.changed")
async def go_plan(ctx, params: EmptyParams) -> ActionResult:
    """Switch to Content Plan view."""
    await save_ui_state(ctx, {"active_view": "plan", "plan_filter": "all"})
    return ActionResult.success({}, summary="Switched to Content Plan")


@chat.function("go_plan_ideas", description="Switch to Content Plan showing only Idea status items.", action_type="read", event="seo.nav.changed")
async def go_plan_ideas(ctx, params: EmptyParams) -> ActionResult:
    """Filter Content Plan to show only Idea items."""
    await save_ui_state(ctx, {"active_view": "plan", "plan_filter": "idea"})
    return ActionResult.success({}, summary="Plan: Ideas")


@chat.function("go_plan_writing", description="Switch to Content Plan showing only Writing status items.", action_type="read", event="seo.nav.changed")
async def go_plan_writing(ctx, params: EmptyParams) -> ActionResult:
    """Filter Content Plan to show only Writing items."""
    await save_ui_state(ctx, {"active_view": "plan", "plan_filter": "writing"})
    return ActionResult.success({}, summary="Plan: Writing")


@chat.function("go_plan_review", description="Switch to Content Plan showing only Review status items.", action_type="read", event="seo.nav.changed")
async def go_plan_review(ctx, params: EmptyParams) -> ActionResult:
    """Filter Content Plan to show only Review items."""
    await save_ui_state(ctx, {"active_view": "plan", "plan_filter": "review"})
    return ActionResult.success({}, summary="Plan: Review")


@chat.function("go_plan_done", description="Switch to Content Plan showing only Published/Done items.", action_type="read", event="seo.nav.changed")
async def go_plan_done(ctx, params: EmptyParams) -> ActionResult:
    """Filter Content Plan to show only Published items."""
    await save_ui_state(ctx, {"active_view": "plan", "plan_filter": "published"})
    return ActionResult.success({}, summary="Plan: Done")


@chat.function("go_rankings", description="Switch main panel to Rankings view.", action_type="read", event="seo.nav.changed")
async def go_rankings(ctx, params: EmptyParams) -> ActionResult:
    """Switch to Rankings view."""
    await save_ui_state(ctx, {"active_view": "rankings"})
    return ActionResult.success({}, summary="Switched to Rankings")


@chat.function("go_keywords", description="Switch main panel to Keyword Research view.", action_type="read", event="seo.nav.changed")
async def go_keywords(ctx, params: EmptyParams) -> ActionResult:
    """Switch to Keyword Research view."""
    await save_ui_state(ctx, {"active_view": "keywords"})
    return ActionResult.success({}, summary="Switched to Keywords")


@chat.function("go_settings", description="Switch main panel to Settings view.", action_type="read", event="seo.nav.changed")
async def go_settings(ctx, params: EmptyParams) -> ActionResult:
    """Switch to Settings view."""
    await save_ui_state(ctx, {"active_view": "settings"})
    return ActionResult.success({}, summary="Switched to Settings")


@chat.function("go_docs", description="Switch main panel to Knowledge Base (docs) view.", action_type="read", event="seo.nav.changed")
async def go_docs(ctx, params: EmptyParams) -> ActionResult:
    """Switch to Knowledge Base view."""
    await save_ui_state(ctx, {"active_view": "docs"})
    return ActionResult.success({}, summary="Switched to Knowledge Base")


@chat.function(
    "open_editor",
    description="Open a specific content item in the editor.",
    action_type="read",
    event="seo.nav.changed",
)
async def open_editor(ctx, params: OpenEditorParams) -> ActionResult:
    """Open a content item in the editor by ID."""
    if not params.content_id:
        return ActionResult.error(error="Select an item from the dropdown first.")
    item = await _get_content(ctx, params.content_id)
    kw         = (item.get("keyword") or item.get("title") or params.content_id) if item else params.content_id
    word_count = len((item.get("content") or "").split()) if item else 0
    status     = item.get("status", "idea") if item else "unknown"
    wp_id      = item.get("wp_post_id", "") if item else ""
    await save_ui_state(ctx, {
        "active_view": "editor",
        "selected_id": params.content_id,
        "editor_mode": "edit",
    })
    return ActionResult.success(
        {
            "content_id":       params.content_id,
            "keyword":          kw,
            "word_count":       word_count,
            "status":           status,
            "wp_post_id":       wp_id,
            "has_open_article": True,
        },
        summary=(
            f"Article open: '{kw}' ({word_count} words, {status}).\n"
            f"article_id={params.content_id}\n"
            f"You can now edit it — tell me what to change (перепиши, улучши, добавь...)."
        ),
    )


@chat.function(
    "set_editor_mode",
    description="Toggle editor between edit and preview mode.",
    action_type="read",
    event="seo.nav.changed",
)
async def set_editor_mode(ctx, params: SetEditorModeParams) -> ActionResult:
    """Set editor display mode to 'edit' or 'preview'."""
    await save_ui_state(ctx, {"editor_mode": params.mode})
    return ActionResult.success({}, summary=f"Editor mode: {params.mode}")


@chat.function("go_preview", description="Switch editor to preview mode.", action_type="read", event="seo.nav.changed")
async def go_preview(ctx, params: EmptyParams) -> ActionResult:
    """Switch editor to preview mode."""
    await save_ui_state(ctx, {"editor_mode": "preview"})
    return ActionResult.success({}, summary="Preview mode")


@chat.function("go_edit", description="Switch editor to edit mode.", action_type="read", event="seo.nav.changed")
async def go_edit(ctx, params: EmptyParams) -> ActionResult:
    """Switch editor to edit mode."""
    await save_ui_state(ctx, {"editor_mode": "edit"})
    return ActionResult.success({}, summary="Edit mode")


@chat.function("show_editor_panel", description="Show the article text editor in Step 3.", action_type="read", event="seo.nav.changed")
async def show_editor_panel(ctx, params: EmptyParams) -> ActionResult:
    """Reveal the rich-text editor in Step 3."""
    await save_ui_state(ctx, {"show_editor": True})
    return ActionResult.success({}, summary="Editor shown")


@chat.function("hide_editor_panel", description="Hide the article text editor in Step 3.", action_type="read", event="seo.nav.changed")
async def hide_editor_panel(ctx, params: EmptyParams) -> ActionResult:
    """Hide the rich-text editor in Step 3."""
    await save_ui_state(ctx, {"show_editor": False})
    return ActionResult.success({}, summary="Editor hidden")


@chat.function(
    "resume_editor",
    description="Return to the editor for the currently open content item.",
    action_type="read",
    event="seo.nav.changed",
)
async def resume_editor(ctx, params: EmptyParams) -> ActionResult:
    """Return to the editor for the currently open article."""
    await save_ui_state(ctx, {"active_view": "editor"})
    return ActionResult.success({}, summary="Returned to editor")


@chat.function(
    "new_content",
    description="Create a new content plan item (blog post or newsletter) and open it in the editor.",
    action_type="write",
    chain_callable=True,
    effects=["create:content"],
    event="seo.content.created",
)
async def new_content(ctx, params: CreateContentParams) -> ActionResult:
    """Create a new content plan item and open it in the editor."""
    data = {
        "keyword": params.keyword,
        "type": params.type,
        "title": params.title or "",
        "content": "",
        "subject": "",
        "status": "idea",
        "volume": params.volume,
        "difficulty": params.difficulty,
        "wp_post_id": None,
        "ml_campaign_id": None,
    }
    item_id = await _create(ctx, data)
    await save_ui_state(ctx, {
        "active_view": "editor",
        "selected_id": item_id,
        "editor_mode": "edit",
    })
    return ActionResult.success(
        {"id": item_id, "keyword": params.keyword},
        summary=f"Created '{params.keyword}' ({params.type}) and opened in editor",
    )


@chat.function(
    "import_from_wp",
    description=(
        "Import an existing WordPress post into the Content Plan for editing. "
        "Use when user wants to edit an existing WP article, draft, or post that was not created through this extension. "
        "Accepts post ID or keyword/title to find the post. "
        "After import, the post is available in Content Plan and can be edited, improved, or republished."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:content"],
    event="seo.content.created",
)
async def import_from_wp(ctx, params: ImportFromWpParams) -> ActionResult:
    """Pull a WP post into Content Plan so Webbee can edit it."""
    from wpb_app import load_settings, create_content
    from api_client import _post

    s = await load_settings(ctx)
    if not s.get("wp_app_password"):
        return ActionResult.error(error="WordPress not configured. Add credentials in Settings.")

    # Fetch post from WP via MOS
    data = await _post(ctx, "/api/wordpress/get", {
        "wp_url":      s["wp_url"],
        "wp_user":     s["wp_username"],
        "wp_password": s["wp_app_password"],
        "post_id":     params.post_id,
    }) if params.post_id else {}

    # If no post_id, search by keyword in recent posts
    if not data or "error" in data:
        posts_data = await _post(ctx, "/api/wordpress/list", {
            "wp_url":      s["wp_url"],
            "wp_user":     s["wp_username"],
            "wp_password": s["wp_app_password"],
            "per_page":    50,
            "status":      "any",
        })
        posts = posts_data.get("posts", []) if "error" not in posts_data else []
        q = (params.keyword_hint or "").lower()
        match = next(
            (p for p in posts if q in (p.get("title") or "").lower() or q in (p.get("slug") or "").lower()),
            None
        )
        if not match:
            titles = [p.get("title", "")[:40] for p in posts[:10]]
            return ActionResult.error(
                error=f"Post '{params.keyword_hint}' not found in WordPress. Available: {', '.join(titles)}"
            )
        # Fetch full content
        data = await _post(ctx, "/api/wordpress/get", {
            "wp_url":      s["wp_url"],
            "wp_user":     s["wp_username"],
            "wp_password": s["wp_app_password"],
            "post_id":     match["id"],
        })

    if "error" in data:
        return ActionResult.error(error=f"Failed to fetch post: {data['error']}")

    title   = data.get("title", "Imported post")
    content = data.get("content", "")
    slug    = data.get("slug", "")
    wp_id   = data.get("id")
    # keyword = slug → spaces
    keyword = slug.replace("-", " ") if slug else title[:40].lower()

    item_id = await create_content(ctx, {
        "keyword":    keyword,
        "title":      title,
        "content":    content,
        "status":     "review",
        "type":       "blog",
        "wp_post_id": wp_id,
        "slug":       slug,
    })
    await save_ui_state(ctx, {"active_view": "editor", "selected_id": item_id, "editor_mode": "edit"})

    return ActionResult.success(
        {"item_id": item_id, "content_id": item_id, "wp_post_id": wp_id, "title": title},
        summary=(
            f"✅ Imported '{title}' (WP #{wp_id}) into Content Plan. item_id={item_id}\n"
            f"Article is now in Review status and open in editor.\n"
            f"You can now edit it — use patch_article or improve_article with item_id={item_id}."
        ),
    )

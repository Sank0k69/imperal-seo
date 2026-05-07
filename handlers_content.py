"""Content CRUD handlers (save/update/delete/brief). AI writing moved to handlers_ai_write.py."""
import time

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, delete_content, load_settings, load_ui_state
from api_client import generate_brief as _mos_brief, log_action
from params import SaveDraftParams, UpdateStatusParams, DeleteContentParams, AiBriefParams, SaveBriefParams, PatchArticleParams


async def _resolve_id(ctx, content_id: str) -> str:
    """Return content_id if set, else use the currently open editor item."""
    if content_id:
        return content_id
    state = await load_ui_state(ctx)
    return state.get("selected_id", "")


@chat.function(
    "save_draft",
    description="Save title and HTML content from the editor to the content store.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def save_draft(ctx, params: SaveDraftParams) -> ActionResult:
    """Save title and HTML content from the editor."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id)
    try:
        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, "save_draft", cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")
        updates = {}
        if params.title:   updates["title"]   = params.title
        if params.content: updates["content"] = params.content
        if params.subject: updates["subject"] = params.subject
        if updates:
            await update_content(ctx, cid, updates)
        await log_action(ctx, "save_draft", cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success({"id": cid}, summary=f"Draft saved: {params.title or item.get('title', '...')}")
    except Exception as e:
        await log_action(ctx, "save_draft", cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))


@chat.function(
    "update_status",
    description="Move a content item to a new status: idea, writing, review, or published.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def update_status(ctx, params: UpdateStatusParams) -> ActionResult:
    """Update the status of a content item."""
    valid = {"idea", "writing", "review", "published"}
    if params.status not in valid:
        return ActionResult.error(error=f"Invalid status '{params.status}'. Use: {', '.join(valid)}")
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")
    await update_content(ctx, cid, {"status": params.status})
    return ActionResult.success({"id": cid, "status": params.status}, summary=f"Status → {params.status}: {item.get('keyword', '')}")


@chat.function(
    "delete_content",
    description="Delete a content plan item permanently.",
    action_type="write",
    chain_callable=True,
    effects=["delete:content"],
    event="seo.content.deleted",
)
async def delete_content_fn(ctx, params: DeleteContentParams) -> ActionResult:
    """Permanently delete a content item."""
    item = await get_content(ctx, params.content_id)
    if not item:
        return ActionResult.error(error="Content item not found")
    await delete_content(ctx, params.content_id)
    return ActionResult.success({"id": params.content_id}, summary=f"Deleted: {item.get('keyword', params.content_id)}")


@chat.function(
    "generate_brief",
    description="Generate an SEO content brief: title, meta description, H2/H3 outline, search intent. Saved and shown in the editor.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def generate_brief(ctx, params: AiBriefParams) -> ActionResult:
    """Generate an SEO content brief via MOS AI."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id)
    try:
        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, "generate_brief", cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")

        kw           = item.get("keyword", "")
        content_type = item.get("type", "blog")
        vol          = item.get("volume", 0)
        diff         = item.get("difficulty", 0)
        s            = await load_settings(ctx)
        language     = s.get("language", "en")

        data = await _mos_brief(ctx, keyword=kw, content_type=content_type,
                                volume=vol, difficulty=diff,
                                extra=params.extra or "", language=language)
        if "error" in data:
            await log_action(ctx, "generate_brief", cid, int((time.monotonic() - t0) * 1000), False, data["error"])
            return ActionResult.error(error=data["error"])

        brief_text = data.get("brief", "")
        await update_content(ctx, cid, {"brief": brief_text, "status": "writing"})
        await log_action(ctx, "generate_brief", cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success(
            {"brief": brief_text[:300]},
            summary=f"Brief ready for '{kw}' — visible in Step 1 of the editor.",
        )
    except Exception as e:
        await log_action(ctx, "generate_brief", cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))


@chat.function(
    "save_brief",
    description="Save manually edited brief text.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def save_brief(ctx, params: SaveBriefParams) -> ActionResult:
    """Save edited brief text."""
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")
    await update_content(ctx, cid, {"brief": params.brief_text})
    return ActionResult.success({"id": cid}, summary="Brief saved.")


@chat.function(
    "patch_article",
    description=(
        "Edit the current article content based on an instruction. "
        "Examples: 'add hello world at the beginning', 'replace intro with X', "
        "'add outbound link to Y in section Z', 'shorten the conclusion'. "
        "Use for direct content edits — NOT for full rewrites (use improve_article for that)."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def patch_article(ctx, params: PatchArticleParams) -> ActionResult:
    """Apply a specific edit to the article content via AI on MOS server."""
    from api_client import generate_brief as _mos_brief, log_action, _post
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="No article open. Open an article from the Content Plan first.")

    content = item.get("content", "")
    if not content:
        return ActionResult.error(error="Article has no content yet. Generate it first with ai_write.")

    data = await _post(ctx, "/api/content/refine", {
        "user_key":    "",
        "content":     content,
        "instruction": params.instruction,
        "keyword":     item.get("keyword", ""),
    }, timeout=60)

    if "error" in data:
        return ActionResult.error(error=data["error"])

    new_content = data.get("content", content)
    await update_content(ctx, cid, {"content": new_content})

    return ActionResult.success(
        {"changed": new_content != content},
        summary=f"Article updated: '{params.instruction[:60]}'. Saved to draft.",
    )

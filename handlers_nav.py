"""Navigation handlers + content creation."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, save_ui_state, create_content as _create, get_content as _get_content
from params import OpenEditorParams, CreateContentParams, SetEditorModeParams, EmptyParams


@chat.function("go_plan", description="Switch main panel to Content Plan view.", action_type="read", event="seo.nav.changed")
async def go_plan(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"active_view": "plan"})
    return ActionResult.success({}, summary="Switched to Content Plan")


@chat.function("go_rankings", description="Switch main panel to Rankings view.", action_type="read", event="seo.nav.changed")
async def go_rankings(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"active_view": "rankings"})
    return ActionResult.success({}, summary="Switched to Rankings")


@chat.function("go_keywords", description="Switch main panel to Keyword Research view.", action_type="read", event="seo.nav.changed")
async def go_keywords(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"active_view": "keywords"})
    return ActionResult.success({}, summary="Switched to Keywords")


@chat.function("go_settings", description="Switch main panel to Settings view.", action_type="read", event="seo.nav.changed")
async def go_settings(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"active_view": "settings"})
    return ActionResult.success({}, summary="Switched to Settings")


@chat.function("go_docs", description="Switch main panel to Knowledge Base (docs) view.", action_type="read", event="seo.nav.changed")
async def go_docs(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"active_view": "docs"})
    return ActionResult.success({}, summary="Switched to Knowledge Base")


@chat.function(
    "open_editor",
    description="Open a specific content item in the editor.",
    action_type="read",
    event="seo.nav.changed",
)
async def open_editor(ctx, params: OpenEditorParams) -> ActionResult:
    item = await _get_content(ctx, params.content_id)
    kw = (item.get("keyword") or item.get("title") or params.content_id) if item else params.content_id
    await save_ui_state(ctx, {
        "active_view": "editor",
        "selected_id": params.content_id,
        "editor_mode": "edit",
    })
    return ActionResult.success(
        {"content_id": params.content_id},
        summary=f"Opened '{kw}' in editor",
    )


@chat.function(
    "set_editor_mode",
    description="Toggle editor between edit and preview mode.",
    action_type="read",
    event="seo.nav.changed",
)
async def set_editor_mode(ctx, params: SetEditorModeParams) -> ActionResult:
    await save_ui_state(ctx, {"editor_mode": params.mode})
    return ActionResult.success({}, summary=f"Editor mode: {params.mode}")


@chat.function("go_preview", description="Switch editor to preview mode.", action_type="read", event="seo.nav.changed")
async def go_preview(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"editor_mode": "preview"})
    return ActionResult.success({}, summary="Preview mode")


@chat.function("go_edit", description="Switch editor to edit mode.", action_type="read", event="seo.nav.changed")
async def go_edit(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"editor_mode": "edit"})
    return ActionResult.success({}, summary="Edit mode")


@chat.function("show_editor_panel", description="Show the article text editor in Step 3.", action_type="read", event="seo.nav.changed")
async def show_editor_panel(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"show_editor": True})
    return ActionResult.success({}, summary="Editor shown")


@chat.function("hide_editor_panel", description="Hide the article text editor in Step 3.", action_type="read", event="seo.nav.changed")
async def hide_editor_panel(ctx, params: EmptyParams) -> ActionResult:
    await save_ui_state(ctx, {"show_editor": False})
    return ActionResult.success({}, summary="Editor hidden")


@chat.function(
    "resume_editor",
    description="Return to the editor for the currently open content item.",
    action_type="read",
    event="seo.nav.changed",
)
async def resume_editor(ctx, params: EmptyParams) -> ActionResult:
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
    """Create a content item and navigate to the editor."""
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

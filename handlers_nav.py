"""Navigation handlers + content creation."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, save_ui_state, create_content as _create
from params import OpenEditorParams, CreateContentParams, SetEditorModeParams, EmptyParams


@chat.function("go_plan", description="Switch main panel to Content Plan view.", action_type="read")
async def go_plan(ctx, params: EmptyParams) -> ActionResult:
    """Switch to the content plan list view."""
    await save_ui_state(ctx, {"active_view": "plan"})
    return ActionResult.success({}, summary="Switched to Content Plan")


@chat.function("go_rankings", description="Switch main panel to Rankings view.", action_type="read")
async def go_rankings(ctx, params: EmptyParams) -> ActionResult:
    """Switch to the keyword rankings view."""
    await save_ui_state(ctx, {"active_view": "rankings"})
    return ActionResult.success({}, summary="Switched to Rankings")


@chat.function("go_keywords", description="Switch main panel to Keyword Research view.", action_type="read")
async def go_keywords(ctx, params: EmptyParams) -> ActionResult:
    """Switch to the keyword research view."""
    await save_ui_state(ctx, {"active_view": "keywords"})
    return ActionResult.success({}, summary="Switched to Keywords")


@chat.function("go_settings", description="Switch main panel to Settings view.", action_type="read")
async def go_settings(ctx, params: EmptyParams) -> ActionResult:
    """Switch to the settings view."""
    await save_ui_state(ctx, {"active_view": "settings"})
    return ActionResult.success({}, summary="Switched to Settings")


@chat.function("go_docs", description="Switch main panel to Knowledge Base (docs) view.", action_type="read")
async def go_docs(ctx, params: EmptyParams) -> ActionResult:
    """Switch to the knowledge base documentation view."""
    await save_ui_state(ctx, {"active_view": "docs"})
    return ActionResult.success({}, summary="Switched to Knowledge Base")


@chat.function(
    "open_editor",
    description="Open a specific content item in the editor.",
    action_type="read",
)
async def open_editor(ctx, params: OpenEditorParams) -> ActionResult:
    """Open a content plan item in the full editor view."""
    await save_ui_state(ctx, {
        "active_view": "editor",
        "selected_id": params.content_id,
        "editor_mode": "edit",
    })
    return ActionResult.success(
        {"content_id": params.content_id},
        summary=f"Opened item {params.content_id} in editor",
    )


@chat.function(
    "set_editor_mode",
    description="Toggle editor between edit and preview mode.",
    action_type="read",
)
async def set_editor_mode(ctx, params: SetEditorModeParams) -> ActionResult:
    """Switch editor between write mode and rendered preview mode."""
    await save_ui_state(ctx, {"editor_mode": params.mode})
    return ActionResult.success({}, summary=f"Editor mode: {params.mode}")


@chat.function(
    "new_content",
    description="Create a new content plan item (blog post or newsletter) and open it in the editor.",
    action_type="write",
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

"""Publishing handlers — WordPress only. Newsletter is copy-paste (no API)."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, load_settings
from app import save_settings as _save_settings
from api_wordpress import create_post, update_post
from params import PublishWpParams, SaveSettingsParams


@chat.function(
    "publish_wp",
    description="Create or update a WordPress post from a blog content item. status: 'draft' or 'publish'.",
    action_type="write",
    event="seo.content.published",
)
async def publish_wp(ctx, params: PublishWpParams) -> ActionResult:
    """Create or update a WordPress post from a content item."""
    s = await load_settings(ctx)
    if not s.get("wp_app_password"):
        return ActionResult.error(
            "WordPress Application Password not configured. "
            "Go to Settings, or generate one in WP Admin → Users → Profile → Application Passwords."
        )

    item = await get_content(ctx, params.content_id)
    if not item:
        return ActionResult.error("Content item not found")

    title = item.get("title") or item.get("keyword", "Untitled")
    content = item.get("content", "")
    if not content:
        return ActionResult.error("Content is empty — write or generate a draft first.")

    wp_post_id = item.get("wp_post_id")
    wp_url = s["wp_url"]
    username = s["wp_username"]
    app_pw = s["wp_app_password"]
    author_id = int(s.get("wp_author_id", 3))

    if wp_post_id:
        post = await update_post(
            ctx, wp_url, username, app_pw,
            post_id=int(wp_post_id),
            title=title,
            content=content,
            status=params.status,
        )
        action = "updated"
    else:
        post = await create_post(
            ctx, wp_url, username, app_pw,
            title=title,
            content=content,
            status=params.status,
            author_id=author_id,
        )
        action = "created"

    if not post.get("id"):
        return ActionResult.error(f"WordPress returned an unexpected response: {post}")

    new_status = "published" if params.status == "publish" else item.get("status", "review")
    await update_content(ctx, params.content_id, {
        "wp_post_id": post["id"],
        "target_url": post.get("link", ""),
        "status": new_status,
    })

    return ActionResult.success(
        {"wp_id": post["id"], "link": post.get("link", ""), "wp_status": params.status},
        summary=f"Post {action} on WordPress (ID {post['id']}, status: {params.status}). {post.get('link', '')}",
    )


@chat.function(
    "save_settings",
    description="Save API keys and configuration for SE Ranking and WordPress.",
    action_type="write",
    event="seo.settings.saved",
)
async def save_settings_fn(ctx, params: SaveSettingsParams) -> ActionResult:
    """Save SE Ranking and WordPress API credentials."""
    updated = await _save_settings(ctx, params.model_dump(exclude_none=True))
    keys_set = [
        k for k, v in updated.items()
        if v and (k.endswith("_key") or k.endswith("_password"))
    ]
    return ActionResult.success(
        {"updated": list(updated.keys())},
        summary=f"Settings saved. Credentials configured: {', '.join(keys_set) or 'none'}",
    )

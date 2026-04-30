"""Publishing handlers — WordPress publish + SEO meta setup."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, load_settings, load_ui_state
from app import save_settings as _save_settings
from api_wordpress import create_post, update_post
from params import PublishWpParams, SaveSettingsParams, SetWpSeoParams


async def _resolve_id(ctx, content_id: str) -> str:
    if content_id:
        return content_id
    state = await load_ui_state(ctx)
    return state.get("selected_id", "")


@chat.function(
    "publish_wp",
    description="Create or update a WordPress post from a blog content item. status: 'draft' or 'publish'.",
    action_type="write",
    event="seo.content.published",
)
async def publish_wp(ctx, params: PublishWpParams) -> ActionResult:
    s = await load_settings(ctx)
    if not s.get("wp_app_password"):
        return ActionResult.error(error=(
            "WordPress Application Password not configured. "
            "Go to Settings → WordPress → Application Passwords."
        ))

    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    title   = item.get("title") or item.get("keyword", "Untitled")
    content = item.get("content", "")
    if not content:
        return ActionResult.error(error="Content is empty — run AI Write first.")

    wp_post_id = item.get("wp_post_id")
    wp_url     = s["wp_url"]
    username   = s["wp_username"]
    app_pw     = s["wp_app_password"]
    author_id  = int(s.get("wp_author_id", 3))

    if wp_post_id:
        post = await update_post(ctx, wp_url, username, app_pw, post_id=int(wp_post_id), title=title, content=content, status=params.status)
        action = "updated"
    else:
        post = await create_post(ctx, wp_url, username, app_pw, title=title, content=content, status=params.status, author_id=author_id)
        action = "created"

    if not post.get("id"):
        return ActionResult.error(error=f"WordPress error: {post}")

    new_status = "published" if params.status == "publish" else item.get("status", "review")
    await update_content(ctx, cid, {
        "wp_post_id": post["id"],
        "target_url": post.get("link", ""),
        "status": new_status,
    })

    return ActionResult.success(
        {"wp_id": post["id"], "link": post.get("link", ""), "wp_status": params.status},
        summary=f"Post {action} on WordPress (ID {post['id']}, status: {params.status}). {post.get('link', '')}",
    )


@chat.function(
    "set_wp_seo",
    description=(
        "Set Yoast SEO fields on the WordPress post: focus keyword and meta description. "
        "Call this after publish_wp to complete SEO setup."
    ),
    action_type="write",
    event="seo.content.updated",
)
async def set_wp_seo(ctx, params: SetWpSeoParams) -> ActionResult:
    s = await load_settings(ctx)
    if not s.get("wp_app_password"):
        return ActionResult.error(error="WordPress not configured. Go to Settings.")

    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    wp_post_id = item.get("wp_post_id")
    if not wp_post_id:
        return ActionResult.error(error="Publish to WordPress first, then set SEO.")

    focus_kw   = params.focus_keyword or item.get("keyword", "")
    meta_desc  = params.meta_description

    # If no meta description provided, generate one from title/keyword
    if not meta_desc:
        title = item.get("title") or item.get("keyword", "")
        result = await ctx.ai.complete(
            f"Write a compelling SEO meta description for this article.\n"
            f"Title: {title}\nKeyword: {focus_kw}\n\n"
            "Rules: 120-160 characters, include the keyword naturally, no quotes, no trailing period."
        )
        meta_desc = (getattr(result, "text", None) or str(result)).strip().strip('"').strip("'")[:160]

    # Update Yoast meta via WP REST API
    post = await update_post(
        ctx,
        s["wp_url"], s["wp_username"], s["wp_app_password"],
        post_id=int(wp_post_id),
        meta={
            "_yoast_wpseo_focuskw":   focus_kw,
            "_yoast_wpseo_metadesc":  meta_desc,
        },
    )

    if not post.get("id"):
        return ActionResult.error(error=f"WP meta update failed: {post}")

    await update_content(ctx, cid, {"meta_description": meta_desc, "focus_keyword": focus_kw})
    return ActionResult.success(
        {"focus_keyword": focus_kw, "meta_description": meta_desc},
        summary=f"SEO set — keyword: '{focus_kw}', meta: '{meta_desc[:60]}...'",
    )


@chat.function(
    "save_settings",
    description="Save API keys and configuration for SE Ranking and WordPress.",
    action_type="write",
    event="seo.settings.saved",
)
async def save_settings_fn(ctx, params: SaveSettingsParams) -> ActionResult:
    updated = await _save_settings(ctx, params.model_dump(exclude_none=True))
    keys_set = [k for k, v in updated.items() if v and (k.endswith("_key") or k.endswith("_password"))]
    return ActionResult.success(
        {"updated": list(updated.keys())},
        summary=f"Settings saved. Credentials configured: {', '.join(keys_set) or 'none'}",
    )

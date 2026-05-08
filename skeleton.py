"""Skeleton context providers — inject live data into Webbee LLM context."""
from app import ext, load_ui_state, get_content, load_settings, list_content


@ext.skeleton("current_article", ttl=60,
              description="Currently open article in editor — keyword, title, word count, status, id")
async def refresh_current_article(ctx) -> dict:
    """Inject open article context so Webbee knows what's being edited."""
    state = await load_ui_state(ctx)
    selected_id = state.get("selected_id")
    active_view  = state.get("active_view", "plan")

    if not selected_id:
        return {"response": {
            "has_open_article": False,
            "instruction": "No article open. Ask user to open one from Content Plan.",
        }}

    item = await get_content(ctx, selected_id)
    if not item:
        return {"response": {
            "has_open_article": False,
            "instruction": "Article not found in storage.",
        }}

    content = item.get("content", "")
    word_count = len(content.split()) if content else 0

    return {"response": {
        "has_open_article": True,
        "article_id":   selected_id,
        "keyword":      item.get("keyword", ""),
        "title":        item.get("title", ""),
        "status":       item.get("status", "idea"),
        "type":         item.get("type", "blog"),
        "word_count":   word_count,
        "wp_post_id":   str(item.get("wp_post_id") or ""),
        "has_content":  word_count > 50,
        "view":         active_view,
        "instruction": (
            f"User is editing article '{item.get('keyword') or item.get('title', 'untitled')}' "
            f"({word_count} words, status: {item.get('status', 'idea')}). "
            f"article_id={selected_id}. "
            f"Use patch_article or improve_article with this article_id."
        ),
    }}


@ext.skeleton("content_overview", ttl=120,
              description="Content plan summary — total items, counts by status")
async def refresh_content_overview(ctx) -> dict:
    """Inject content plan summary so Webbee knows the overall state."""
    try:
        items = await list_content(ctx)
    except Exception:
        items = []

    counts = {"idea": 0, "writing": 0, "review": 0, "published": 0}
    for i in items:
        s = i.get("status", "idea")
        counts[s] = counts.get(s, 0) + 1

    return {"response": {
        "total_articles": len(items),
        "ideas":          counts["idea"],
        "writing":        counts["writing"],
        "in_review":      counts["review"],
        "published":      counts["published"],
        "instruction": (
            f"{len(items)} articles in content plan: "
            f"{counts['idea']} ideas, {counts['writing']} writing, "
            f"{counts['review']} review, {counts['published']} published."
        ),
    }}


@ext.skeleton("wp_config", ttl=600,
              description="WordPress and SE Ranking connection status")
async def refresh_wp_config(ctx) -> dict:
    """Inject connection status so Webbee knows what's available."""
    s = await load_settings(ctx)
    wp_ok  = bool(s.get("wp_app_password") and s.get("wp_url"))
    ser_ok = bool(s.get("seranking_data_key"))

    return {"response": {
        "wordpress_connected": wp_ok,
        "seranking_connected": ser_ok,
        "wp_url":    s.get("wp_url", ""),
        "domain":    s.get("seranking_domain", ""),
        "instruction": (
            ("WordPress connected. " if wp_ok else "WordPress NOT connected — go to Settings. ")
            + ("SE Ranking connected." if ser_ok else "SE Ranking NOT connected — go to Settings.")
        ),
    }}

"""Skeleton context providers — inject background facts into Webbee LLM context.

Per SDK docs: skeleton = eventually consistent background facts (slow-changing data).
For active UI state (open article), handlers read ctx.store directly.
Skeleton TTLs: current_article=30s, content_overview=120s, wp_config=600s.
"""
from wpb_app import ext, load_ui_state, get_content, load_settings, list_content


@ext.skeleton("current_article", ttl=30,
              description="Currently open article in editor — keyword, title, word count, status, article_id")
async def refresh_current_article(ctx) -> dict:
    """Slow-changing background fact: which article is in the editor."""
    state = await load_ui_state(ctx)
    selected_id = state.get("selected_id")

    if not selected_id:
        return {"response": {
            "has_open_article": False,
            "article_id": "",
            "keyword": "",
            "word_count": 0,
            "instruction": "No article is open in the editor.",
        }}

    item = await get_content(ctx, selected_id)
    if not item:
        return {"response": {
            "has_open_article": False,
            "article_id": selected_id,
            "instruction": "Article ID set but not found — may have been deleted.",
        }}

    content = item.get("content", "")
    word_count = len(content.split()) if content else 0
    kw = item.get("keyword") or item.get("title", "untitled")

    return {"response": {
        "has_open_article": True,
        "article_id": selected_id,
        "keyword": kw,
        "title": item.get("title", ""),
        "status": item.get("status", "idea"),
        "word_count": word_count,
        "wp_post_id": str(item.get("wp_post_id") or ""),
        "has_content": word_count > 50,
        "instruction": (
            f"OPEN ARTICLE: '{kw}' | {word_count} words | status={item.get('status','idea')} | "
            f"article_id={selected_id} | wp_post_id={item.get('wp_post_id','')}. "
            f"Use article_id={selected_id} with patch_article/improve_article/check_article_quality."
        ),
    }}


@ext.skeleton("content_overview", ttl=120,
              description="Content plan totals: ideas, writing, review, published counts")
async def refresh_content_overview(ctx) -> dict:
    """Background snapshot of content plan state."""
    try:
        items = await list_content(ctx)
    except Exception:
        items = []

    counts = {"idea": 0, "writing": 0, "review": 0, "published": 0}
    in_wp = 0
    for i in items:
        s = i.get("status", "idea")
        counts[s] = counts.get(s, 0) + 1
        if i.get("wp_post_id"):
            in_wp += 1

    return {"response": {
        "total": len(items),
        "ideas": counts["idea"],
        "writing": counts["writing"],
        "review": counts["review"],
        "published": counts["published"],
        "in_wordpress": in_wp,
        "instruction": (
            f"Content plan: {len(items)} total — "
            f"{counts['idea']} ideas, {counts['writing']} writing, "
            f"{counts['review']} in review, {counts['published']} published, "
            f"{in_wp} synced to WordPress."
        ),
    }}


@ext.skeleton("wp_config", ttl=600,
              description="WordPress + SE Ranking connection status and domain")
async def refresh_wp_config(ctx) -> dict:
    """Background config fact — changes rarely."""
    s = await load_settings(ctx)
    wp_ok  = bool(s.get("wp_app_password") and s.get("wp_url"))
    ser_ok = bool(s.get("seranking_data_key"))
    proj_ok = bool(s.get("seranking_project_key"))

    return {"response": {
        "wordpress_connected": wp_ok,
        "seranking_data_connected": ser_ok,
        "seranking_project_connected": proj_ok,
        "wp_url": s.get("wp_url", ""),
        "blog_domain": s.get("seranking_domain", ""),
        "instruction": (
            f"WordPress: {'✓ connected' if wp_ok else '✗ NOT connected — Settings needed'}. "
            f"SE Ranking data: {'✓' if ser_ok else '✗ NOT configured'}. "
            f"SE Ranking tracking: {'✓' if proj_ok else '✗ NOT configured'}. "
            f"Domain: {s.get('seranking_domain','not set')}."
        ),
    }}

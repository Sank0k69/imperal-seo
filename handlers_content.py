"""Content CRUD and AI writing handlers."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, delete_content, save_ui_state, load_settings, load_ui_state
from api_client import keywords_for_article, generate_article as _mos_generate, generate_brief as _mos_brief, generate_newsletter_mos as _mos_newsletter
from handlers_docs import build_docs_context
from params import SaveDraftParams, UpdateStatusParams, DeleteContentParams, AiBriefParams, AiWriteParams, GenerateNewsletterParams


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
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")
    updates = {}
    if params.title:   updates["title"]   = params.title
    if params.content: updates["content"] = params.content
    if params.subject: updates["subject"] = params.subject
    if updates:
        await update_content(ctx, cid, updates)
    return ActionResult.success({"id": cid}, summary=f"Draft saved: {params.title or item.get('title', '...')}")


@chat.function(
    "update_status",
    description="Move a content item to a new status: idea, writing, review, or published.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def update_status(ctx, params: UpdateStatusParams) -> ActionResult:
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
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
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
        return ActionResult.error(error=data["error"])

    brief_text = data.get("brief", "")
    await update_content(ctx, cid, {"brief": brief_text, "status": "writing"})
    return ActionResult.success(
        {"brief": brief_text[:300]},
        summary=f"Brief ready for '{kw}' — visible in Step 1 of the editor.",
    )


@chat.function(
    "ai_write",
    description=(
        "Generate a full SEO + AI-optimized article. "
        "Phase 1: enrich keyword set (secondary KWs, LSI, FAQ questions). "
        "Phase 2: write via MOS content engine with structured output. "
        "section: full | improve"
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def ai_write(ctx, params: AiWriteParams) -> ActionResult:
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    kw           = item.get("keyword", "")
    content_type = item.get("type", "blog")
    existing     = item.get("content", "")
    brief        = item.get("brief", "")
    title        = item.get("title", kw)
    s            = await load_settings(ctx)
    language     = s.get("language", "en")

    # Newsletter — delegate to MOS
    if content_type == "newsletter":
        news_text = existing or item.get("subject", kw) or kw
        data = await _mos_newsletter(ctx, news_text=news_text)
        if "error" in data:
            return ActionResult.error(error=data["error"])
        draft_html   = data.get("content", "")
        subject_line = data.get("subject", "")
        updates: dict = {"content": draft_html, "status": "review"}
        if subject_line and not item.get("subject"): updates["subject"] = subject_line
        if subject_line and not item.get("title"):   updates["title"]   = subject_line
        await update_content(ctx, cid, updates)
        return ActionResult.success({"length": len(draft_html)}, summary=f"Newsletter draft written for '{kw}'")

    # Improve mode — MOS /refine
    if params.section == "improve":
        if not existing:
            return ActionResult.error(error="No content to improve. Run AI Write first.")
        from api_client import _post
        data = await _post(ctx, "/api/content/refine", {
            "user_key":    "",
            "content":     existing,
            "instruction": (
                f"Improve this article about '{kw}' for SEO and AI-search visibility. "
                "Add a FAQ section if missing. Improve readability. Make answers more direct."
            ),
        }, timeout=120)
        if "error" in data:
            return ActionResult.error(error=data["error"])
        draft_html = data.get("content", existing)
        await update_content(ctx, cid, {"content": draft_html})
        return ActionResult.success({"length": len(draft_html)}, summary=f"Article improved for '{kw}'")

    # Full write — Phase 1: enrich keywords via MOS + load brand context in parallel
    import asyncio
    kw_data, brand_context = await asyncio.gather(
        keywords_for_article(ctx, kw),
        build_docs_context(ctx),
    )
    secondary  = kw_data.get("secondary_keywords", []) if "error" not in kw_data else []
    lsi        = kw_data.get("lsi_terms", [])           if "error" not in kw_data else []
    questions  = kw_data.get("questions", [])            if "error" not in kw_data else []
    word_count = kw_data.get("word_count", 1400)         if "error" not in kw_data else 1400
    title_opts = kw_data.get("title_options", [])        if "error" not in kw_data else []

    # Use first title option if item has no title yet
    best_title = title_opts[0] if title_opts and not item.get("title") else title

    # SE Ranking context: current position for this keyword
    ser_context = ""
    current_position = item.get("difficulty")  # we store rank as difficulty? no — use volume/difficulty as SEO signals
    if item.get("volume") or item.get("difficulty"):
        ser_context = (
            f"Keyword: {kw} | Volume: {item.get('volume', 0)}/mo | Difficulty: {item.get('difficulty', 0)}/100"
        )

    # Phase 2: write via MOS content engine
    article_type = params.article_type or item.get("type", "blog")
    # If brief exists, prepend it to ser_context so MOS uses it as outline
    if brief:
        ser_context = f"CONTENT BRIEF (follow this outline):\n{brief}\n\n{ser_context}".strip()

    data = await _mos_generate(
        ctx,
        topic=best_title or kw,
        keyword=kw,
        article_type=article_type,
        word_count=word_count,
        language=language,
        secondary_keywords=secondary,
        lsi_terms=lsi,
        questions=questions,
        brand_context=brand_context,
        ser_context=ser_context,
    )

    if "error" in data:
        return ActionResult.error(error=data["error"])

    draft_html   = data.get("content", "")
    final_title  = data.get("title", best_title or kw)
    meta_desc    = data.get("meta_description", "")
    faq_schema   = data.get("faq_schema", "")
    kw_used      = data.get("word_count", 0)

    updates = {
        "content":            draft_html,
        "status":             "review",
        "secondary_keywords": secondary,
        "meta_description":   meta_desc,
        "faq_schema":         faq_schema,
    }
    if final_title and final_title != kw:
        updates["title"] = final_title

    await update_content(ctx, cid, updates)
    return ActionResult.success(
        {"length": len(draft_html), "word_count": kw_used, "secondary_keywords": len(secondary)},
        summary=(
            f"Article written for '{kw}' (~{kw_used} words).\n"
            f"Title: {final_title}\n"
            f"Secondary KWs: {', '.join(secondary[:3])}{'...' if len(secondary) > 3 else ''}\n"
            f"FAQ: {'included' if questions else 'none'}"
        ),
    )


@chat.function(
    "generate_newsletter",
    description="Write a newsletter from a news item or topic. Uses brand voice from Settings.",
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def generate_newsletter(ctx, params: GenerateNewsletterParams) -> ActionResult:
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    data = await _mos_newsletter(ctx, news_text=params.news_text, tone_note=params.tone_note or "")
    if "error" in data:
        return ActionResult.error(error=data["error"])

    newsletter_html = data.get("content", "")
    subject_line    = data.get("subject", "")

    updates: dict = {"content": newsletter_html, "status": "review"}
    if subject_line and not item.get("subject"): updates["subject"] = subject_line
    if subject_line and not item.get("title"):   updates["title"]   = subject_line

    await update_content(ctx, cid, updates)
    await save_ui_state(ctx, {"editor_mode": "preview"})
    return ActionResult.success({"subject": subject_line, "length": len(newsletter_html)}, summary=f"Newsletter written. Subject: {subject_line}")

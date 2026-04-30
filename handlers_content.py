"""Content CRUD and AI writing handlers."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, get_content, update_content, delete_content, save_ui_state, load_settings, load_ui_state
from api_client import keywords_for_article, generate_article as _mos_generate
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
    event="seo.content.deleted",
)
async def delete_content_fn(ctx, params: DeleteContentParams) -> ActionResult:
    item = await get_content(ctx, params.content_id)
    if not item:
        return ActionResult.error(error="Content item not found")
    await delete_content(ctx, params.content_id)
    return ActionResult.success({"id": params.content_id}, summary=f"Deleted: {item.get('keyword', params.content_id)}")


@chat.function(
    "ai_brief",
    description="Generate a content brief with outline using AI. Saves to the content item.",
    action_type="write",
    event="seo.content.updated",
)
async def ai_brief(ctx, params: AiBriefParams) -> ActionResult:
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    kw = item.get("keyword", "")
    content_type = item.get("type", "blog")
    vol = item.get("volume", 0)
    diff = item.get("difficulty", 0)

    docs_ctx = await build_docs_context(ctx)
    docs_block = f"\n\nBRAND DOCUMENTATION:\n{docs_ctx}" if docs_ctx else ""

    system = (
        "You are a senior SEO content strategist. "
        "Write in clear, practical English. Focus on search intent and conversion."
        + docs_block
    )

    if content_type == "newsletter":
        prompt = (
            f"Create a newsletter brief for the topic: '{kw}'.\n"
            f"Extra context: {params.extra}\n\n"
            "Include: subject line options (3), goal, audience pain point, "
            "main message, CTA, and a 5-section outline."
        )
    else:
        prompt = (
            f"Create an SEO blog post brief for the keyword: '{kw}'\n"
            f"Search volume: {vol}/mo | Difficulty: {diff}/100\n"
            f"Extra context: {params.extra}\n\n"
            "Include: search intent, target reader, recommended title (H1), "
            "meta description (120-160 chars), 6-8 section outline with H2/H3 suggestions, "
            "and 3 internal link opportunities."
        )

    result = await ctx.ai.complete(f"{system}\n\n{prompt}")
    brief_text = getattr(result, "text", None) or str(result)

    await update_content(ctx, cid, {"content": f"<pre>{brief_text}</pre>", "status": "writing"})
    return ActionResult.success({"brief": brief_text[:300]}, summary=f"Brief generated for '{kw}'")


@chat.function(
    "ai_write",
    description=(
        "Generate a full SEO + AI-optimized article. "
        "Phase 1: enrich keyword set (secondary KWs, LSI, FAQ questions). "
        "Phase 2: write via MOS content engine with structured output. "
        "section: full | improve"
    ),
    action_type="write",
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
    title        = item.get("title", kw)
    s            = await load_settings(ctx)
    language     = s.get("language", "en")

    # Newsletter uses direct AI (different flow)
    if content_type == "newsletter":
        docs_ctx = await build_docs_context(ctx)
        docs_block = f"\n\nBRAND DOCUMENTATION:\n{docs_ctx}" if docs_ctx else ""
        system = (
            "You are a professional content writer. "
            "Output valid HTML (use <h2>, <h3>, <p>, <ul>, <li>, <strong>). "
            "Do not include <html>, <head>, <body> tags." + docs_block
        )
        subject = item.get("subject", kw)
        prompt = (
            f"Write a complete HTML email newsletter.\n"
            f"Subject: {subject}\nTopic: {kw}\nBrief/outline:\n{existing}\n\n"
            "300-500 words. Clear CTA at the end. Personal and valuable."
        )
        result = await ctx.ai.complete(f"{system}\n\n{prompt}")
        draft_html = getattr(result, "text", None) or str(result)
        await update_content(ctx, cid, {"content": draft_html, "status": "review"})
        return ActionResult.success({"length": len(draft_html)}, summary=f"Newsletter draft written for '{kw}'")

    # Improve mode — use MOS refine
    if params.section == "improve":
        if not existing:
            return ActionResult.error(error="No content to improve. Run AI Write first.")
        docs_ctx = await build_docs_context(ctx)
        docs_block = f"\n\nBRAND DOCUMENTATION:\n{docs_ctx}" if docs_ctx else ""
        system = (
            "You are a professional content writer. "
            "Output valid HTML. Do not include <html>, <head>, <body> tags." + docs_block
        )
        prompt = (
            f"Improve this article about '{kw}' for SEO and AI-search visibility.\n"
            "Add a FAQ section if missing. Improve readability. Make answers more direct.\n\n"
            f"Current content:\n{existing}"
        )
        result = await ctx.ai.complete(f"{system}\n\n{prompt}")
        draft_html = getattr(result, "text", None) or str(result)
        await update_content(ctx, cid, {"content": draft_html})
        return ActionResult.success({"length": len(draft_html)}, summary=f"Article improved for '{kw}'")

    # Full write — Phase 1: enrich keywords via MOS
    kw_data = await keywords_for_article(ctx, kw)
    secondary = kw_data.get("secondary_keywords", []) if "error" not in kw_data else []
    lsi       = kw_data.get("lsi_terms", [])           if "error" not in kw_data else []
    questions = kw_data.get("questions", [])            if "error" not in kw_data else []
    word_count = kw_data.get("word_count", 1400)        if "error" not in kw_data else 1400
    title_opts = kw_data.get("title_options", [])       if "error" not in kw_data else []

    # Use first title option if item has no title yet
    best_title = title_opts[0] if title_opts and not item.get("title") else title

    # Phase 2: write via MOS content engine
    article_type = item.get("type", "blog")
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
    event="seo.content.updated",
)
async def generate_newsletter(ctx, params: GenerateNewsletterParams) -> ActionResult:
    cid = await _resolve_id(ctx, params.content_id)
    item = await get_content(ctx, cid)
    if not item:
        return ActionResult.error(error="Content item not found")

    s = await load_settings(ctx)
    company     = s.get("company_name") or "our company"
    description = s.get("brand_description") or ""
    voice       = s.get("brand_voice") or "Direct and smart. Short punchy sentences. No corporate fluff."
    cta         = s.get("newsletter_cta") or "Learn more"
    site        = s.get("site_url") or ""
    blog        = s.get("blog_url") or ""
    tg          = s.get("tg_url") or ""
    community   = s.get("community_url") or ""

    links_block = "\n".join(filter(None, [
        f"• Telegram: {tg}" if tg else "",
        f"• Blog: {blog}" if blog else "",
        f"• Site: {site}" if site else "",
        f"• Community: {community}" if community else "",
    ]))

    docs_ctx = await build_docs_context(ctx)
    docs_block = f"\n\nBRAND DOCUMENTATION:\n{docs_ctx}" if docs_ctx else ""

    brand_section = (
        f"COMPANY: {company}\n"
        f"{f'About: {description}' if description else ''}\n"
        f"VOICE: {voice}\nCTA text: \"{cta}\"\n"
        if company and company != "our company"
        else "Use your knowledge about this company and its brand voice.\n"
    )

    system = f"""You are writing an email newsletter.

{brand_section}
RULES: Write as the company. No fake urgency, no exaggerated claims, no corporate speak.

OUTPUT FORMAT:
SUBJECT: [subject line, max 50 chars]
PREVIEW: [preview text, 80-100 chars]
---
[body: 150-300 words, HTML]
---
LINKS:
{links_block if links_block else '(add links in Settings → Brand)'}{docs_block}"""

    tone = f"\n\nTone note: {params.tone_note}" if params.tone_note else ""
    prompt = f"Write a newsletter based on:\n\n{params.news_text}{tone}"

    result = await ctx.ai.complete(f"{system}\n\n{prompt}")
    newsletter_html = getattr(result, "text", None) or str(result)

    subject_line = ""
    for line in newsletter_html.splitlines():
        if line.startswith("SUBJECT:"):
            subject_line = line.replace("SUBJECT:", "").strip()
            break

    updates: dict = {"content": newsletter_html, "status": "review"}
    if subject_line and not item.get("subject"): updates["subject"] = subject_line
    if subject_line and not item.get("title"):   updates["title"]   = subject_line

    await update_content(ctx, cid, updates)
    await save_ui_state(ctx, {"editor_mode": "preview"})
    return ActionResult.success({"subject": subject_line, "length": len(newsletter_html)}, summary=f"Newsletter written. Subject: {subject_line}")

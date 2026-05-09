"""AI article writing handlers (ai_write, check_article_job)."""
import asyncio
import time

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from wpb_app import chat, get_content, update_content, load_settings, save_ui_state
from api_client import (keywords_for_article, start_generate_article,
                        poll_article_job, generate_newsletter_mos as _mos_newsletter,
                        log_action, _post)
from handlers_content import _resolve_id
from handlers_docs import build_docs_context
from params import AiWriteParams, AiBriefParams


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
    """Start AI article generation (async job via MOS)."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id)
    try:
        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")

        kw           = item.get("keyword", "")
        content_type = item.get("type", "blog")
        existing     = item.get("content", "")
        brief        = item.get("brief", "")
        title        = item.get("title", kw)
        s            = await load_settings(ctx)
        language     = s.get("language", "en")

        if content_type == "newsletter":
            news_text = existing or item.get("subject", kw) or kw
            data = await _mos_newsletter(ctx, news_text=news_text)
            if "error" in data:
                await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), False, data["error"])
                return ActionResult.error(error=data["error"])
            draft_html   = data.get("content", "")
            subject_line = data.get("subject", "")
            updates: dict = {"content": draft_html, "status": "review"}
            if subject_line and not item.get("subject"): updates["subject"] = subject_line
            if subject_line and not item.get("title"):   updates["title"]   = subject_line
            await update_content(ctx, cid, updates)
            await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), True)
            return ActionResult.success({"length": len(draft_html)}, summary=f"Newsletter draft written for '{kw}'")

        if params.section == "improve":
            if not existing:
                await log_action(ctx, "ai_write_improve", cid, int((time.monotonic() - t0) * 1000), False, "No content to improve")
                return ActionResult.error(error="No content to improve. Run AI Write first.")
            data = await _post(ctx, "/api/content/refine", {
                "user_key":    "",
                "content":     existing,
                "instruction": (
                    f"Improve this article about '{kw}' for SEO and AI-search visibility. "
                    "Add a FAQ section if missing. Improve readability. Make answers more direct."
                ),
            }, timeout=120)
            if "error" in data:
                await log_action(ctx, "ai_write_improve", cid, int((time.monotonic() - t0) * 1000), False, data["error"])
                return ActionResult.error(error=data["error"])
            draft_html = data.get("content", existing)
            await update_content(ctx, cid, {"content": draft_html})
            await log_action(ctx, "ai_write_improve", cid, int((time.monotonic() - t0) * 1000), True)
            return ActionResult.success({"length": len(draft_html)}, summary=f"Article improved for '{kw}'")

        kw_data, brand_context = await asyncio.gather(
            keywords_for_article(ctx, kw),
            build_docs_context(ctx),
        )
        secondary  = kw_data.get("secondary_keywords", []) if "error" not in kw_data else []
        lsi        = kw_data.get("lsi_terms", [])           if "error" not in kw_data else []
        questions  = kw_data.get("questions", [])            if "error" not in kw_data else []
        word_count = kw_data.get("word_count", 1400)         if "error" not in kw_data else 1400
        title_opts = kw_data.get("title_options", [])        if "error" not in kw_data else []

        best_title = title_opts[0] if title_opts and not item.get("title") else title

        ser_context = ""
        if item.get("volume") or item.get("difficulty"):
            ser_context = (
                f"Keyword: {kw} | Volume: {item.get('volume', 0)}/mo | Difficulty: {item.get('difficulty', 0)}/100"
            )

        article_type = params.article_type or item.get("type", "blog")
        if brief:
            ser_context = f"CONTENT BRIEF (follow this outline):\n{brief}\n\n{ser_context}".strip()

        job = await start_generate_article(
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

        if "error" in job:
            await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), False, job["error"])
            return ActionResult.error(error=job["error"])

        job_id = job.get("job_id", "")
        await update_content(ctx, cid, {
            "generating":         True,
            "job_id":             job_id,
            "secondary_keywords": secondary,
            "title":              best_title or kw,
        })
        await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success(
            {"job_id": job_id, "status": "pending"},
            summary=(
                f"Article generation started for '{kw}' (job: {job_id}).\n"
                f"Takes ~60-90 seconds. Use check_article_job to retrieve the result."
            ),
        )
    except Exception as e:
        await log_action(ctx, "ai_write", cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))


@chat.function(
    "check_article_job",
    description=(
        "Check if background article generation has completed. "
        "Call after ai_write to retrieve the finished article. "
        "Returns 'pending' if still generating, saves and shows article when done."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:content"],
    event="seo.content.updated",
)
async def check_article_job(ctx, params: AiBriefParams) -> ActionResult:
    """Poll for a completed article generation job."""
    t0 = time.monotonic()
    cid = await _resolve_id(ctx, params.content_id)
    try:
        item = await get_content(ctx, cid)
        if not item:
            await log_action(ctx, "check_article_job", cid, int((time.monotonic() - t0) * 1000), False, "Content item not found")
            return ActionResult.error(error="Content item not found")

        job_id = item.get("job_id", "")
        if not job_id:
            return ActionResult.error(error="No active generation job. Run 'Write Full Article' first.")

        data = await poll_article_job(ctx, job_id)
        status = data.get("status", "not_found")

        if status == "pending":
            return ActionResult.success(
                {"status": "pending", "job_id": job_id},
                summary="Article is still generating. Check again in ~30 seconds.",
            )

        if status in ("not_found", "error"):
            await update_content(ctx, cid, {"generating": False, "job_id": None})
            err = data.get("error", "Generation failed — please try again.")
            await log_action(ctx, "check_article_job", cid, int((time.monotonic() - t0) * 1000), False, err)
            return ActionResult.error(error=err)

        result      = data.get("result", {})
        draft_html  = result.get("content", "")
        final_title = result.get("title", "")
        meta_desc   = result.get("meta_description", "")
        faq_schema  = result.get("faq_schema", "")
        kw_used     = result.get("word_count", 0)
        secondary   = item.get("secondary_keywords", [])

        updates = {"content": draft_html, "status": "review", "generating": False, "job_id": None}
        if meta_desc:   updates["meta_description"] = meta_desc
        if faq_schema:  updates["faq_schema"]        = faq_schema
        if final_title and final_title != item.get("keyword", ""):
            updates["title"] = final_title

        await update_content(ctx, cid, updates)
        await save_ui_state(ctx, {"editor_mode": "preview"})

        kw = item.get("keyword", "")
        await log_action(ctx, "check_article_job", cid, int((time.monotonic() - t0) * 1000), True)
        return ActionResult.success(
            {"length": len(draft_html), "word_count": kw_used},
            summary=(
                f"Article ready for '{kw}' (~{kw_used} words).\n"
                f"Title: {final_title}\n"
                f"Secondary KWs: {', '.join(secondary[:3])}{'...' if len(secondary) > 3 else ''}"
            ),
        )
    except Exception as e:
        await log_action(ctx, "check_article_job", cid, int((time.monotonic() - t0) * 1000), False, str(e))
        return ActionResult.error(error=str(e))

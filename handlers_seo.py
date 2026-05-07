"""SE Ranking handlers — keywords, gaps, rankings, content plan."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, save_ui_state, create_content
from api_client import ser_keywords, ser_gaps, ser_rankings, ser_projects, content_plan
from params import FetchKeywordsParams, FetchGapsParams, FetchRankingsParams, ListProjectsParams, BuildPlanParams, SetupBlogStyleParams


@chat.function(
    "fetch_keywords",
    description="Fetch organic keywords for the domain from SE Ranking. Shows position, volume, difficulty.",
    action_type="read",
    event="seo.nav.changed",
)
async def fetch_keywords(ctx, params: FetchKeywordsParams) -> ActionResult:
    """Fetch organic keywords for the domain from SE Ranking."""
    s = await load_settings(ctx)
    domain = params.domain or s.get("seranking_domain", "")
    source = params.source or s.get("seranking_source", "us")
    if not domain:
        return ActionResult.error(error="Domain not configured. Go to Settings → SE Ranking.")

    data = await ser_keywords(ctx, domain, source, params.limit, params.min_volume, params.max_difficulty)
    if "error" in data:
        return ActionResult.error(error=data["error"])

    kws = data.get("keywords", [])
    await save_ui_state(ctx, {"active_view": "keywords", "kw_results": kws[:100]})

    top = kws[:5]
    lines = [f"- {k.get('keyword')} pos:{k.get('position')} vol:{k.get('volume')} diff:{k.get('difficulty')}" for k in top]
    return ActionResult.success(
        {"count": len(kws), "keywords": kws},
        summary=f"Found {len(kws)} keywords for {domain}:\n" + "\n".join(lines),
    )


@chat.function(
    "fetch_gaps",
    description="Find keyword gaps — keywords the competitor ranks for but our domain does not.",
    action_type="read",
    event="seo.nav.changed",
)
async def fetch_gaps(ctx, params: FetchGapsParams) -> ActionResult:
    """Fetch keyword gaps vs a competitor domain."""
    s = await load_settings(ctx)
    if not s.get("seranking_data_key"):
        return ActionResult.error(error="SE Ranking Data API key not configured. Go to Settings.")
    domain = s.get("seranking_domain", "")
    source = params.source or s.get("seranking_source", "us")
    if not domain:
        return ActionResult.error(error="Domain not configured. Go to Settings → SE Ranking.")

    data = await ser_gaps(ctx, domain, params.competitor, source, params.limit)
    if "error" in data:
        return ActionResult.error(error=data["error"])

    gaps = data.get("keywords", [])
    await save_ui_state(ctx, {"active_view": "keywords", "kw_results": gaps[:100]})

    top = gaps[:5]
    lines = [f"- {k.get('keyword')} vol:{k.get('volume')} diff:{k.get('difficulty')}" for k in top]
    return ActionResult.success(
        {"count": len(gaps), "keywords": gaps, "competitor": params.competitor},
        summary=f"Found {len(gaps)} gap keywords vs {params.competitor}:\n" + "\n".join(lines),
    )


@chat.function(
    "fetch_rankings",
    description="Fetch keyword rankings from SE Ranking project (position tracking).",
    action_type="read",
    event="seo.nav.changed",
)
async def fetch_rankings(ctx, params: FetchRankingsParams) -> ActionResult:
    """Fetch tracked keyword rankings from SE Ranking."""
    data = await ser_rankings(ctx)
    if "error" in data:
        return ActionResult.error(error=data["error"])

    rankings = data.get("rankings", [])
    await save_ui_state(ctx, {"active_view": "rankings", "rankings_results": rankings[:200]})

    top = sorted(rankings, key=lambda r: r.get("position", 999))[:5]
    lines = [f"- #{r.get('position')} {r.get('keyword')} → {(r.get('url') or '/')[-50:]}" for r in top]
    return ActionResult.success(
        {"count": len(rankings), "rankings": rankings},
        summary=f"Loaded {len(rankings)} tracked keywords.\nTop 5:\n" + "\n".join(lines),
    )


@chat.function(
    "list_ser_projects",
    description="List SE Ranking projects — use this to find the project_id for settings.",
    action_type="read",
)
async def list_ser_projects(ctx, params: ListProjectsParams) -> ActionResult:
    """List all SE Ranking projects to find the project ID."""
    data = await ser_projects(ctx)
    if "error" in data:
        return ActionResult.error(error=data["error"])

    projects = data.get("projects", [])
    lines = [f"- {p.get('id')} — {p.get('name', p.get('site', '?'))}" for p in projects[:20]]
    return ActionResult.success(
        {"projects": projects},
        summary="SE Ranking projects:\n" + "\n".join(lines),
    )


@chat.function(
    "build_content_plan",
    description=(
        "Generate a 5-article content plan using SE Ranking keyword data and AI. "
        "Automatically avoids topics already published on the blog. "
        "Creates content items in the plan ready for writing."
    ),
    action_type="write",
    chain_callable=True,
    effects=["create:content"],
    event="seo.content.created",
)
async def build_content_plan(ctx, params: BuildPlanParams) -> ActionResult:
    """AI-generate a 5-article content plan from SE Ranking data."""
    s = await load_settings(ctx)
    if not s.get("seranking_data_key"):
        return ActionResult.error(error="SE Ranking Data API key not configured. Go to Settings.")
    if not s.get("seranking_domain"):
        return ActionResult.error(error="Domain not configured. Go to Settings → SE Ranking.")

    language = params.language or "en"
    competitor = params.competitor or s.get("seranking_competitor", "")

    data = await content_plan(ctx, competitor=competitor, language=language)
    if "error" in data:
        return ActionResult.error(error=f"Content plan failed: {data['error']}")

    articles = data.get("articles", [])
    if not articles:
        return ActionResult.error(error="AI returned no articles. Try again or check SE Ranking data.")

    created = 0
    for a in articles:
        await create_content(ctx, {
            "keyword":    a.get("keyword", ""),
            "type":       a.get("article_type", "blog"),
            "title":      a.get("title", ""),
            "content":    "",
            "subject":    "",
            "status":     "idea",
            "volume":     a.get("volume", 0),
            "difficulty": a.get("difficulty", 0),
            "intent":     a.get("intent", ""),
            "priority":   a.get("priority", ""),
            "angle":      a.get("angle", ""),
            "wp_post_id": None,
            "ml_campaign_id": None,
        })
        created += 1

    kw_used = data.get("keywords_used", 0)
    gaps_used = data.get("gaps_used", 0)
    return ActionResult.success(
        {"created": created, "keywords_used": kw_used, "gaps_used": gaps_used},
        summary=(
            f"Content plan ready: {created} articles added to the plan.\n"
            f"Based on {kw_used} keywords{f' + {gaps_used} gap keywords' if gaps_used else ''}.\n"
            "Open Content Plan to see them."
        ),
    )


@chat.function(
    "setup_blog_style",
    description=(
        "Analyze a blog URL and create a writing style profile for that blog. "
        "Use when user provides their blog URL and wants articles written in their style. "
        "Crawls RSS feed, analyzes recent posts, generates writing instructions."
    ),
    action_type="write",
    chain_callable=True,
    effects=["update:settings"],
    event="seo.settings.saved",
)
async def setup_blog_style(ctx, params: SetupBlogStyleParams) -> ActionResult:
    """Analyze blog writing style and save as active brand profile."""
    from app import save_settings
    from api_client import _post
    from handlers_docs import _load_docs
    from imperal_sdk import ui

    s = await load_settings(ctx)
    blog_url = params.blog_url or s.get("blog_url", "")
    if not blog_url:
        return ActionResult.error(error="Provide your blog URL. Example: setup_blog_style with blog_url=https://blog.yourdomain.com")

    data = await _post(ctx, "/api/content/analyze_blog_style", {
        "blog_url":          blog_url,
        "language":          s.get("language", "en"),
        "posts_to_analyze":  5,
    }, timeout=90)

    if "error" in data:
        return ActionResult.error(error=data["error"])

    profile_text = data.get("profile", "")
    posts_count  = data.get("posts_analyzed", 0)

    # Save as MOS brand profile named "blog_style"
    save_result = await _post(ctx, "/api/profiles/save", {
        "name":    "blog_style",
        "content": profile_text,
    })
    if "error" not in save_result:
        await save_settings(ctx, {"active_profile": "blog_style"})

    return ActionResult.success(
        {"profile_name": "blog_style", "posts_analyzed": posts_count},
        summary=(
            f"Blog style analyzed from {posts_count} posts at {blog_url}.\n"
            "Profile 'blog_style' created and set as active — all new articles will follow this style."
        ),
        ui=ui.Stack(children=[
            ui.Alert(
                message=f"Writing style set from {blog_url} ({posts_count} posts analyzed). "
                        "Profile 'blog_style' is now active.",
                type="success",
            ),
            ui.Text(content=profile_text[:600] + "...", variant="caption"),
        ]),
    )

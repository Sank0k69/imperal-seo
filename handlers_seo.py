"""SE Ranking handlers — keywords, gaps, rankings."""
from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, load_settings, save_ui_state
from api_seranking import domain_keywords, keyword_gaps, project_rankings, list_projects
from params import FetchKeywordsParams, FetchGapsParams, FetchRankingsParams, ListProjectsParams


@chat.function(
    "fetch_keywords",
    description="Fetch organic keywords for the domain from SE Ranking Data API. Shows position, volume, difficulty.",
    action_type="read",
)
async def fetch_keywords(ctx, params: FetchKeywordsParams) -> ActionResult:
    """Fetch organic keywords for a domain from SE Ranking Data API."""
    s = await load_settings(ctx)
    key = s.get("seranking_data_key", "")
    if not key:
        return ActionResult.error("SE Ranking Data API key not configured. Go to Settings.")

    domain = params.domain or s.get("seranking_domain", "blog.webhostmost.com")
    source = params.source or s.get("seranking_source", "us")

    kws = await domain_keywords(
        ctx, key, domain, source,
        limit=params.limit,
        min_volume=params.min_volume,
        max_difficulty=params.max_difficulty,
    )

    await save_ui_state(ctx, {
        "active_view": "keywords",
        "kw_results": kws[:100],
    })

    top = kws[:5]
    summary_lines = [
        f"• {k.get('keyword')} — pos {k.get('position')}, vol {k.get('volume')}, diff {k.get('difficulty')}"
        for k in top
    ]
    return ActionResult.success(
        {"count": len(kws), "keywords": kws},
        summary=f"Found {len(kws)} keywords for {domain}:\n" + "\n".join(summary_lines),
    )


@chat.function(
    "fetch_gaps",
    description="Find keyword gaps — what the competitor ranks for but our domain doesn't.",
    action_type="read",
)
async def fetch_gaps(ctx, params: FetchGapsParams) -> ActionResult:
    """Find gap keywords — what the competitor ranks for but our domain does not."""
    s = await load_settings(ctx)
    key = s.get("seranking_data_key", "")
    if not key:
        return ActionResult.error("SE Ranking Data API key not configured. Go to Settings.")

    domain = s.get("seranking_domain", "blog.webhostmost.com")
    source = params.source or s.get("seranking_source", "us")

    gaps = await keyword_gaps(ctx, key, domain, params.competitor, source, params.limit)

    await save_ui_state(ctx, {
        "active_view": "keywords",
        "kw_results": gaps[:100],
    })

    top = gaps[:5]
    summary_lines = [
        f"• {k.get('keyword')} — vol {k.get('volume')}, diff {k.get('difficulty')}"
        for k in top
    ]
    return ActionResult.success(
        {"count": len(gaps), "keywords": gaps, "competitor": params.competitor},
        summary=f"Found {len(gaps)} gap keywords vs {params.competitor}:\n" + "\n".join(summary_lines),
    )


@chat.function(
    "fetch_rankings",
    description="Fetch keyword rankings from the configured SE Ranking project (position tracking).",
    action_type="read",
)
async def fetch_rankings(ctx, params: FetchRankingsParams) -> ActionResult:
    """Fetch current keyword ranking positions from the SE Ranking project."""
    s = await load_settings(ctx)
    key = s.get("seranking_project_key", "")
    project_id = s.get("seranking_project_id", "")

    if not key:
        return ActionResult.error("SE Ranking Project API key not configured. Go to Settings.")
    if not project_id:
        return ActionResult.error("SE Ranking Project ID not configured. Go to Settings.")

    rankings = await project_rankings(ctx, key, project_id)

    await save_ui_state(ctx, {
        "active_view": "rankings",
        "rankings_results": rankings[:200],
    })

    top = sorted(rankings, key=lambda r: r.get("position", 999))[:5]
    summary_lines = [
        f"• #{r.get('position')} {r.get('keyword')} → {(r.get('url') or '/')[-50:]}"
        for r in top
    ]
    return ActionResult.success(
        {"count": len(rankings), "rankings": rankings},
        summary=f"Loaded {len(rankings)} tracked keywords.\nTop 5:\n" + "\n".join(summary_lines),
    )


@chat.function(
    "list_ser_projects",
    description="List SE Ranking projects — use this to find the project_id for settings.",
    action_type="read",
)
async def list_ser_projects(ctx, params: ListProjectsParams) -> ActionResult:
    """List SE Ranking projects — use to find the project_id for settings."""
    s = await load_settings(ctx)
    key = s.get("seranking_project_key", "")
    if not key:
        return ActionResult.error("SE Ranking Project API key not configured. Go to Settings.")

    projects = await list_projects(ctx, key)
    lines = [f"• {p.get('id')} — {p.get('name', p.get('site', '?'))}" for p in projects[:20]]
    return ActionResult.success(
        {"projects": projects},
        summary="SE Ranking projects:\n" + "\n".join(lines),
    )

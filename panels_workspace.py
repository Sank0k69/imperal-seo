"""Main workspace panel — plan | editor | rankings | keywords | settings."""
from __future__ import annotations

from imperal_sdk import ui

from app import ext, load_settings, load_ui_state, list_content, ser_ready, wp_ready
from panels_editor import editor_view
from panels_docs import _docs_view
from handlers_docs import _load_docs

REFRESH = (
    "on_event:seo.content.created,seo.content.updated,"
    "seo.content.deleted,seo.content.published,seo.settings.saved,seo.nav.changed"
)


@ext.panel("workspace", slot="center", title="SEO & Content", icon="FileText",
           default_width=860, refresh=REFRESH)
async def workspace_panel(ctx):
    state = await load_ui_state(ctx)
    view = state.get("active_view", "plan")

    if view == "editor":
        return await editor_view(ctx, state)
    if view == "rankings":
        return await _rankings_view(ctx, state)
    if view == "keywords":
        return await _keywords_view(ctx, state)
    if view == "settings":
        return await _settings_view(ctx)
    if view == "docs":
        return await _docs_view(ctx, await _load_docs(ctx))
    return await _plan_view(ctx, state)


# ── Plan view ─────────────────────────────────────────────────────────────────

async def _plan_view(ctx, state: dict) -> ui.UINode:
    items = await list_content(ctx)
    plan_filter = state.get("plan_filter") or "all"
    filtered = [i for i in items if i.get("status") == plan_filter] if plan_filter not in ("all", "") else items

    _filter_label = {
        "idea": "Ideas", "writing": "Writing", "review": "Review", "published": "Done",
    }
    title = f"Content Plan — {_filter_label.get(plan_filter, 'All')}" if plan_filter not in ("all", "") else "Content Plan"

    rows = [
        {
            "keyword":    item.get("keyword", "—"),
            "type":       item.get("type", "blog"),
            "intent":     item.get("intent", "—"),
            "priority":   item.get("priority", "—"),
            "status":     item.get("status", "idea"),
            "volume":     f"{item.get('volume', 0):,}" if item.get("volume") else "—",
            "difficulty": str(item.get("difficulty", "—")),
            "id":         item.get("id", ""),
        }
        for item in filtered
    ]

    empty_msg = (
        f"No items with status '{plan_filter}' yet."
        if plan_filter not in ("all", "")
        else "No content yet. Click 'Build Content Plan (AI)' to generate one."
    )
    table = ui.DataTable(
        columns=[
            ui.DataColumn(key="keyword",    label="Keyword / Topic",  width="28%"),
            ui.DataColumn(key="type",       label="Type",             width="10%"),
            ui.DataColumn(key="intent",     label="Intent",           width="12%"),
            ui.DataColumn(key="priority",   label="Priority",         width="12%"),
            ui.DataColumn(key="status",     label="Status",           width="10%"),
            ui.DataColumn(key="volume",     label="Vol",              width="10%"),
            ui.DataColumn(key="difficulty", label="Diff",             width="8%"),
            ui.DataColumn(key="id",         label="ID",               width="10%"),
        ],
        rows=rows,
    ) if rows else ui.Empty(message=empty_msg)

    header_row_children = [
        ui.Header(text=title, level=3),
        ui.Button(label="+ Find keywords", on_click=ui.Call("go_keywords")),
    ]
    if plan_filter not in ("all", ""):
        header_row_children.append(
            ui.Button(label="× All", on_click=ui.Call("go_plan")),
        )

    build_plan_form = ui.Form(
        action="build_content_plan",
        submit_label="Build Content Plan (AI)",
        children=[],
    )

    open_items = filtered if filtered else items
    open_form = ui.Form(
        action="open_editor",
        submit_label="Open in editor →",
        children=[
            ui.Select(
                param_name="content_id",
                placeholder="Select item to edit",
                options=[
                    {
                        "value": i.get("id", ""),
                        "label": f"{i.get('keyword','')} ({i.get('type','')} · {i.get('status','')})",
                    }
                    for i in open_items
                ],
            ),
        ],
    ) if items else ui.Alert(message="Create your first content item using the panel on the left.", type="info")

    return ui.Stack(children=[
        ui.Stack(children=header_row_children, direction="horizontal", justify="between"),
        build_plan_form,
        table,
        ui.Divider(),
        open_form,
    ])


# ── Rankings view ─────────────────────────────────────────────────────────────

async def _rankings_view(ctx, state: dict) -> ui.UINode:
    rankings = state.get("rankings_results") or []
    refresh_form = ui.Button(label="Refresh rankings", on_click=ui.Call("fetch_rankings"))

    if not rankings:
        return ui.Stack(children=[
            ui.Header(text="Keyword Rankings", level=3),
            ui.Alert(message="No rankings loaded. Click Refresh or configure SE Ranking in Settings.", type="info"),
            refresh_form,
        ])

    rows = [
        {
            "pos": str(r.get("position", "—")),
            "keyword": r.get("keyword", "—"),
            "url": (r.get("url") or "/")[-55:],
            "volume": f"{r.get('volume', 0):,}" if r.get("volume") else "—",
            "diff": str(r.get("difficulty", "—")),
        }
        for r in sorted(rankings, key=lambda x: x.get("position", 9999))[:100]
    ]

    return ui.Stack(children=[
        ui.Stack(children=[
            ui.Header(text="Keyword Rankings", level=3),
            refresh_form,
        ], direction="horizontal", justify="between"),
        ui.DataTable(
            columns=[
                ui.DataColumn(key="pos", label="#", width="8%"),
                ui.DataColumn(key="keyword", label="Keyword", width="40%"),
                ui.DataColumn(key="url", label="Page", width="30%"),
                ui.DataColumn(key="volume", label="Volume", width="12%"),
                ui.DataColumn(key="diff", label="Diff", width="10%"),
            ],
            rows=rows,
        ),
    ])


# ── Keywords view ─────────────────────────────────────────────────────────────

async def _keywords_view(ctx, state: dict) -> ui.UINode:
    kws = state.get("kw_results") or []

    search_form = ui.Form(
        action="fetch_keywords",
        submit_label="Search keywords",
        children=[
            ui.Input(param_name="domain", placeholder="Domain (default: blog.webhostmost.com)"),
            ui.Input(param_name="min_volume", placeholder="Min volume (default: 100)"),
            ui.Input(param_name="max_difficulty", placeholder="Max difficulty (default: 60)"),
            ui.Input(param_name="limit", placeholder="Limit (default: 50)"),
        ],
    )

    gap_form = ui.Form(
        action="fetch_gaps",
        submit_label="Find gaps vs competitor",
        children=[
            ui.Input(param_name="competitor", placeholder="Competitor domain (e.g. hostinger.com)"),
            ui.Input(param_name="limit", placeholder="Limit (default: 30)"),
        ],
    )

    if not kws:
        return ui.Stack(children=[
            ui.Header(text="Keyword Research", level=3),
            search_form,
            ui.Divider(),
            gap_form,
        ])

    rows = [
        {
            "keyword": k.get("keyword", "—"),
            "pos": str(k.get("position", "—")),
            "volume": f"{k.get('volume', 0):,}",
            "diff": str(k.get("difficulty", "—")),
            "cpc": f"${k.get('cpc', 0):.2f}" if k.get("cpc") else "—",
        }
        for k in kws[:100]
    ]

    add_form = ui.Form(
        action="new_content",
        submit_label="Add to content plan",
        children=[
            ui.Input(param_name="keyword", placeholder="Paste keyword from table above"),
            ui.Select(param_name="type", placeholder="Type", options=[
                {"value": "blog", "label": "Blog post"},
                {"value": "newsletter", "label": "Newsletter"},
            ]),
            ui.Input(param_name="volume", placeholder="Volume"),
            ui.Input(param_name="difficulty", placeholder="Difficulty"),
        ],
    )

    return ui.Stack(children=[
        ui.Header(text="Keyword Research", level=3),
        search_form,
        ui.Divider(),
        gap_form,
        ui.Divider(),
        ui.Text(content=f"{len(kws)} keywords found", variant="caption"),
        ui.DataTable(
            columns=[
                ui.DataColumn(key="keyword", label="Keyword", width="40%"),
                ui.DataColumn(key="pos", label="Pos", width="8%"),
                ui.DataColumn(key="volume", label="Volume", width="16%"),
                ui.DataColumn(key="diff", label="Diff", width="10%"),
                ui.DataColumn(key="cpc", label="CPC", width="12%"),
            ],
            rows=rows,
        ),
        ui.Divider(),
        add_form,
    ])


# ── Settings view ─────────────────────────────────────────────────────────────

def _masked(v: str) -> str:
    if not v:
        return ""
    return "••••" + v[-4:] if len(v) > 8 else "••••"


async def _settings_view(ctx) -> ui.UINode:
    s = await load_settings(ctx)

    form = ui.Form(
        action="save_settings",
        submit_label="Save settings",
        children=[
            ui.Header(text="Brand & Newsletter", level=5),
            ui.Text(content="Used in newsletter generation — fill this in first.", variant="caption"),
            ui.Input(param_name="company_name",
                     value=s.get("company_name", ""),
                     placeholder="Company name — e.g. WebHostMost"),
            ui.TextArea(param_name="brand_description",
                        value=s.get("brand_description", ""),
                        placeholder="What your company does (1-2 sentences). Used in the AI prompt.",
                        rows=2),
            ui.TextArea(param_name="brand_voice",
                        value=s.get("brand_voice", ""),
                        placeholder="Voice instruction — e.g. 'Direct and bold. Short sentences. Like a founder talking to users.'",
                        rows=2),
            ui.Input(param_name="newsletter_cta",
                     value=s.get("newsletter_cta", ""),
                     placeholder="Default CTA text — e.g. 'Start your free trial'"),
            ui.Input(param_name="site_url",
                     value=s.get("site_url", ""),
                     placeholder="Site URL — https://yourdomain.com"),
            ui.Input(param_name="blog_url",
                     value=s.get("blog_url", ""),
                     placeholder="Blog URL — https://blog.yourdomain.com"),
            ui.Input(param_name="tg_url",
                     value=s.get("tg_url", ""),
                     placeholder="Telegram channel — https://t.me/yourchannel"),
            ui.Input(param_name="community_url",
                     value=s.get("community_url", ""),
                     placeholder="Community / Forum URL (optional)"),
            ui.Divider(),
            ui.Header(text="SE Ranking", level=5),
            ui.Input(
                param_name="seranking_data_key",
                placeholder=f"Data API key{' (set: ' + _masked(s.get('seranking_data_key','')) + ')' if s.get('seranking_data_key') else ' — seranking.com → Settings → API'}",
            ),
            ui.Input(
                param_name="seranking_project_key",
                placeholder=f"Project API key{' (' + _masked(s.get('seranking_project_key','')) + ')' if s.get('seranking_project_key') else ''}",
            ),
            ui.Input(param_name="seranking_project_id",
                     value=s.get("seranking_project_id", ""),
                     placeholder="Project ID — ask 'list_ser_projects' to find it"),
            ui.Input(param_name="seranking_domain",
                     value=s.get("seranking_domain", ""),
                     placeholder="Your domain — e.g. blog.yourdomain.com"),
            ui.Input(
                param_name="seranking_competitor",
                value=s.get("seranking_competitor", ""),
                placeholder="Competitor domain for gap analysis — e.g. hostinger.com",
            ),
            ui.Divider(),
            ui.Header(text="WordPress", level=5),
            ui.Input(param_name="wp_url",
                     value=s.get("wp_url", ""),
                     placeholder="WordPress URL — https://blog.yourdomain.com"),
            ui.Input(param_name="wp_username",
                     value=s.get("wp_username", ""),
                     placeholder="WP username"),
            ui.Input(
                param_name="wp_app_password",
                placeholder=f"Application Password{' (set)' if s.get('wp_app_password') else ' — WP Admin → Users → Profile → Application Passwords'}",
            ),
            ui.Divider(),
            ui.Header(text="Matomo Analytics (fallback)", level=5),
            ui.Text(content="If Matomo Analytics extension is installed — data is pulled from there automatically. Fill this only if you don't use that extension.", variant="caption"),
            ui.Input(param_name="matomo_url",
                     value=s.get("matomo_url", ""),
                     placeholder="Matomo URL — https://analytics.yourdomain.com"),
            ui.Input(
                param_name="matomo_token",
                placeholder=f"API token{' (set)' if s.get('matomo_token') else ' — Matomo → Settings → Personal → Security → Auth token'}",
            ),
            ui.Input(param_name="matomo_site_id",
                     value=str(s.get("matomo_site_id", "1")),
                     placeholder="Site ID (default: 1)"),
        ],
    )

    return ui.Stack(children=[
        ui.Stack(children=[
            ui.Header(text="Settings", level=3),
            ui.Button(label="← Back", on_click=ui.Call("go_plan")),
        ], direction="horizontal", justify="between"),
        ui.Alert(message="API keys stored encrypted per user.", type="info"),
        form,
    ])

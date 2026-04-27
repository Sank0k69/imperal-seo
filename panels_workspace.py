"""Main workspace panel — plan | editor | rankings | keywords | settings."""
from __future__ import annotations

from imperal_sdk import ui

from app import ext, load_settings, load_ui_state, list_content, ser_ready, wp_ready
from panels_editor import editor_view
from panels_docs import _docs_view
from handlers_docs import _load_docs

REFRESH = (
    "on_event:seo.content.created,seo.content.updated,"
    "seo.content.deleted,seo.content.published,seo.settings.saved"
)


@ext.panel("workspace", slot="right", title="SEO & Content", icon="FileText",
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
    return await _plan_view(ctx)


# ── Plan view ─────────────────────────────────────────────────────────────────

async def _plan_view(ctx) -> ui.UINode:
    items = await list_content(ctx)

    rows = [
        {
            "keyword": item.get("keyword", "—"),
            "type": item.get("type", "blog"),
            "status": item.get("status", "idea"),
            "volume": f"{item.get('volume', 0):,}" if item.get("volume") else "—",
            "difficulty": str(item.get("difficulty", "—")),
            "id": item.get("id", ""),
        }
        for item in items
    ]

    table = ui.DataTable(
        columns=[
            ui.DataColumn(key="keyword", label="Keyword / Topic", width="35%"),
            ui.DataColumn(key="type", label="Type", width="12%"),
            ui.DataColumn(key="status", label="Status", width="13%"),
            ui.DataColumn(key="volume", label="Volume", width="12%"),
            ui.DataColumn(key="difficulty", label="Diff", width="10%"),
            ui.DataColumn(key="id", label="ID", width="18%"),
        ],
        rows=rows,
    ) if rows else ui.Empty(message="No content yet. Add an item using the left panel.")

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
                    for i in items
                ],
            ),
        ],
    ) if items else ui.Alert(message="Create your first content item using the panel on the left.", type="info")

    return ui.Stack(children=[
        ui.Stack(children=[
            ui.Header(text="Content Plan", level=3),
            ui.Form(action="go_keywords", submit_label="+ Find keywords", children=[]),
        ], direction="horizontal", justify="between"),
        table,
        ui.Divider(),
        open_form,
    ])


# ── Rankings view ─────────────────────────────────────────────────────────────

async def _rankings_view(ctx, state: dict) -> ui.UINode:
    rankings = state.get("rankings_results") or []
    refresh_form = ui.Form(action="fetch_rankings", submit_label="Refresh rankings", children=[])

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
        ],
    )

    return ui.Stack(children=[
        ui.Stack(children=[
            ui.Header(text="Settings", level=3),
            ui.Form(action="go_plan", submit_label="← Back", children=[]),
        ], direction="horizontal", justify="between"),
        ui.Alert(message="API keys stored encrypted per user.", type="info"),
        form,
    ])

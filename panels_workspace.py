"""Main workspace panel — plan | editor | rankings | keywords | settings."""
from __future__ import annotations

from imperal_sdk import ui

from app import ext, load_settings, load_ui_state, save_ui_state, list_content, ser_ready, wp_ready
from panels_editor import editor_view
from panels_docs import _docs_view
from panels_settings_view import _settings_view
from handlers_docs import _load_docs

REFRESH = (
    "on_event:seo.content.created,seo.content.updated,"
    "seo.content.deleted,seo.content.published,seo.settings.saved,seo.nav.changed"
)


@ext.panel("editor", slot="center", title="SEO & Content", icon="FileText",
           refresh=REFRESH, center_overlay=True)
async def workspace_panel(ctx, active_view: str = "", plan_filter: str = "", content_id: str = "", **_kw):
    # note_id="board" → undeclared kwarg (Vikunja/Notes pattern for claiming center slot)
    note_id = _kw.get("note_id", "")
    if note_id == "board" and not active_view and not content_id:
        active_view = "plan"

    # No explicit trigger → return None so platform doesn't pre-load into right slot.
    if not content_id and not active_view:
        return None

    state = await load_ui_state(ctx)
    if content_id:
        await save_ui_state(ctx, {"active_view": "editor", "selected_id": content_id})
        state = await load_ui_state(ctx)
    elif active_view:
        updates: dict = {"active_view": active_view}
        if plan_filter:
            updates["plan_filter"] = plan_filter
        await save_ui_state(ctx, updates)
        state = {**state, **updates}
    view = active_view or state.get("active_view", "plan")

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
        ui.Form(action="go_keywords", submit_label="+ Find keywords", children=[]),
    ]
    if plan_filter not in ("all", ""):
        header_row_children.append(
            ui.Form(action="go_plan", submit_label="× All", children=[]),
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
    refresh_btn = ui.Form(action="fetch_rankings", submit_label="↻ Refresh", children=[])

    if not rankings:
        return ui.Page(
            title="SEO Rankings",
            children=[
                ui.Alert(
                    message="No rankings loaded yet. Click Refresh to pull your keyword positions from SE Ranking.",
                    type="info",
                ),
                ui.Form(action="fetch_rankings", submit_label="↻ Load Rankings", children=[]),
            ],
        )

    # ── Compute metrics ────────────────────────────────────────────────────────
    ranked   = [r for r in rankings if r.get("position", 0) > 0]
    top3     = sum(1 for r in ranked if r.get("position", 99) <= 3)
    top10    = sum(1 for r in ranked if r.get("position", 99) <= 10)
    top30    = sum(1 for r in ranked if r.get("position", 99) <= 30)
    top100   = sum(1 for r in ranked if r.get("position", 99) <= 100)
    not_rank = len(rankings) - len(ranked)
    total_vol = sum(r.get("volume", 0) for r in rankings)

    # Change: positive = moved UP (lower position = better)
    gainers = []
    losers  = []
    for r in ranked:
        prev = r.get("previous_position", 0)
        curr = r.get("position", 0)
        if prev and curr and prev != curr:
            change = prev - curr  # positive = moved up
            entry  = {**r, "_change": change}
            if change > 0:
                gainers.append(entry)
            else:
                losers.append(entry)
    gainers = sorted(gainers, key=lambda x: -x["_change"])[:8]
    losers  = sorted(losers,  key=lambda x: x["_change"])[:8]

    # Position distribution for chart
    buckets = {"Top 3": top3, "4-10": top10-top3, "11-30": top30-top10,
               "31-100": top100-top30, "Not ranked": not_rank}
    chart_data = [{"label": k, "value": v} for k, v in buckets.items() if v > 0]

    # ── Header stats ──────────────────────────────────────────────────────────
    stats = ui.Stats(children=[
        ui.Stat(label="Total tracked",  value=str(len(rankings)),   icon="Target"),
        ui.Stat(label="Top 3",          value=str(top3),            color="green",  icon="TrendingUp"),
        ui.Stat(label="Top 10",         value=str(top10),           color="blue",   icon="Award"),
        ui.Stat(label="Top 30",         value=str(top30),           color="yellow", icon="BarChart2"),
        ui.Stat(label="Monthly volume", value=f"{total_vol:,}",     icon="Eye"),
    ])

    # ── Position chart ────────────────────────────────────────────────────────
    chart = ui.Section(title="Position Distribution", children=[
        ui.Chart(
            type="bar",
            data=chart_data,
            x_key="label",
            y_keys=["value"],
            colors={"value": "#3b82f6"},
            height=180,
        ),
    ], collapsible=False)

    # ── Top movers ─────────────────────────────────────────────────────────────
    def _change_label(change: int) -> str:
        return f"▲ {change}" if change > 0 else f"▼ {abs(change)}"

    def _mover_table(items: list, title: str, color: str) -> ui.UINode:
        if not items:
            return ui.Empty(message=f"No {title.lower()} this period")
        rows = [
            {
                "pos":     str(r.get("position", "—")),
                "change":  _change_label(r["_change"]),
                "keyword": r.get("keyword", "—")[:40],
                "vol":     f"{r.get('volume', 0):,}" if r.get("volume") else "—",
            }
            for r in items
        ]
        return ui.DataTable(
            columns=[
                ui.DataColumn(key="pos",     label="#",       width="8%"),
                ui.DataColumn(key="change",  label="Change",  width="15%"),
                ui.DataColumn(key="keyword", label="Keyword", width="57%"),
                ui.DataColumn(key="vol",     label="Vol",     width="20%"),
            ],
            rows=rows,
        )

    movers = ui.Stack(direction="h", gap=3, children=[
        ui.Section(title=f"🚀 Top Gainers ({len(gainers)})", collapsible=False, children=[
            _mover_table(gainers, "Top Gainers", "green"),
        ]),
        ui.Section(title=f"📉 Top Losers ({len(losers)})", collapsible=False, children=[
            _mover_table(losers, "Top Losers", "red"),
        ]),
    ])

    # ── Full table ─────────────────────────────────────────────────────────────
    all_rows = [
        {
            "pos":     str(r.get("position", "—")),
            "prev":    ("▲" if (r.get("previous_position", 0) or 0) > (r.get("position", 0) or 0)
                        else "▼" if (r.get("previous_position", 0) or 0) < (r.get("position", 0) or 0)
                        else "—") if r.get("previous_position") else "—",
            "keyword": r.get("keyword", "—"),
            "url":     (r.get("url") or "")[-45:],
            "vol":     f"{r.get('volume', 0):,}" if r.get("volume") else "—",
        }
        for r in sorted(rankings, key=lambda x: x.get("position", 9999))[:200]
    ]
    full_table = ui.Section(title=f"All Keywords ({len(rankings)})", collapsible=True, children=[
        ui.DataTable(
            columns=[
                ui.DataColumn(key="pos",     label="#",       width="7%"),
                ui.DataColumn(key="prev",    label="±",       width="5%"),
                ui.DataColumn(key="keyword", label="Keyword", width="43%"),
                ui.DataColumn(key="url",     label="Page",    width="30%"),
                ui.DataColumn(key="vol",     label="Vol",     width="15%"),
            ],
            rows=all_rows,
        ),
    ])

    return ui.Page(
        title="SEO Rankings",
        children=[
            ui.Stack(direction="h", justify="between", align="center", children=[
                ui.Text(content="Keyword positions from SE Ranking", variant="caption"),
                refresh_btn,
            ]),
            stats,
            chart,
            movers,
            full_table,
        ],
    )


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


"""Left navigation sidebar + settings panel (right slot).

ui.Tabs is broken — use Forms for navigation (confirmed from analytics ext).
ui.Send is broken — all buttons via ui.Form(action=...).
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext, load_settings, load_ui_state, list_content, ser_ready, wp_ready


def _nav_btn(label: str, action: str, icon: str = "") -> ui.UINode:
    return ui.Form(action=action, submit_label=label, children=[])


@ext.panel("sidebar", slot="left", title="SEO & Content", icon="FileText",
           default_width=220,
           refresh="on_event:seo.content.created,seo.content.updated,seo.settings.saved")
async def sidebar_panel(ctx):
    s = await load_settings(ctx)
    state = await load_ui_state(ctx)
    items = await list_content(ctx)
    active = state.get("active_view", "plan")

    counts = {
        "idea": sum(1 for i in items if i.get("status") == "idea"),
        "writing": sum(1 for i in items if i.get("status") == "writing"),
        "review": sum(1 for i in items if i.get("status") == "review"),
        "published": sum(1 for i in items if i.get("status") == "published"),
    }

    status_badges = ui.Stack(children=[
        ui.Stack(children=[
            ui.Badge(label=f"SE Ranking: {'✓' if ser_ready(s) else '✗'}",
                     color="green" if ser_ready(s) else "red"),
            ui.Badge(label=f"WordPress: {'✓' if wp_ready(s) else '✗'}",
                     color="green" if wp_ready(s) else "red"),
        ], gap=4),
    ])

    selected_id = state.get("selected_id")
    resume_btn_children = []
    if selected_id and active != "editor":
        # Find the keyword/title for the open item
        open_item = next((i for i in items if i.get("id") == selected_id), None)
        label = (open_item.get("keyword") or open_item.get("title") or "item")[:28] if open_item else "item"
        resume_btn_children = [
            ui.Form(action="resume_editor", submit_label=f"↩ Resume: {label}", children=[]),
        ]

    nav = ui.Stack(children=[
        *resume_btn_children,
        _nav_btn("Content Plan", "go_plan", "Layout"),
        _nav_btn("Rankings", "go_rankings", "TrendingUp"),
        _nav_btn("Keywords", "go_keywords", "Search"),
        _nav_btn("Knowledge Base", "go_docs", "BookOpen"),
        _nav_btn("Settings", "go_settings", "Settings"),
    ], gap=4)

    pipeline = ui.Stack(children=[
        ui.Header(text="Pipeline", level=6),
        ui.Stats(children=[
            ui.Stat(label="Ideas", value=str(counts["idea"]), color="gray"),
            ui.Stat(label="Writing", value=str(counts["writing"]), color="blue"),
            ui.Stat(label="Review", value=str(counts["review"]), color="yellow"),
            ui.Stat(label="Done", value=str(counts["published"]), color="green"),
        ]),
    ])

    new_btn = ui.Form(
        action="new_content",
        submit_label="+ New item",
        children=[
            ui.Input(param_name="keyword", placeholder="Keyword or topic"),
            ui.Select(
                param_name="type",
                placeholder="Type",
                options=[
                    {"value": "blog", "label": "Blog post"},
                    {"value": "newsletter", "label": "Newsletter"},
                ],
            ),
        ],
    )

    return ui.Stack(children=[
        ui.Header(text="SEO & Content", level=4),
        status_badges,
        ui.Divider(),
        nav,
        ui.Divider(),
        pipeline,
        ui.Divider(),
        new_btn,
    ])

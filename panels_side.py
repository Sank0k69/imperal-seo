"""Left navigation sidebar."""
from __future__ import annotations

from imperal_sdk import ui

from app import ext, load_settings, load_ui_state, list_content, ser_ready, wp_ready


def _nav_btn(label: str, action: str, icon: str = "") -> ui.UINode:
    return ui.Button(label=label, on_click=ui.Call(action))


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
            ui.Button(label=f"↩ Resume: {label}", on_click=ui.Call("resume_editor")),
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
        ui.Stack(children=[
            ui.Button(label=f"Ideas · {counts['idea']}",     on_click=ui.Call("go_plan_ideas")),
            ui.Button(label=f"Writing · {counts['writing']}", on_click=ui.Call("go_plan_writing")),
            ui.Button(label=f"Review · {counts['review']}",   on_click=ui.Call("go_plan_review")),
            ui.Button(label=f"Done · {counts['published']}",  on_click=ui.Call("go_plan_done")),
        ], direction="horizontal", gap=4, wrap=True),
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

    # Recent articles — status priority: review → writing → published → idea
    _status_order = {"review": 0, "writing": 1, "published": 2, "idea": 3}
    recent = sorted(items, key=lambda x: _status_order.get(x.get("status", "idea"), 3))[:6]

    recent_section_children = []
    if recent:
        total_words = sum(len((i.get("content") or "").split()) for i in items)
        published_count = counts["published"]
        recent_section_children = [
            ui.Header(text="Recent Articles", level=6),
            ui.Text(
                content=f"{len(items)} articles · {total_words:,} words · {published_count} published",
                variant="caption",
            ),
            ui.Form(
                action="open_editor",
                submit_label="Open →",
                children=[
                    ui.Select(
                        param_name="content_id",
                        placeholder="Quick open article...",
                        options=[
                            {
                                "value": i["id"],
                                "label": f"[{i.get('status','?')[:3].upper()}] {(i.get('keyword') or i.get('title') or 'untitled')[:28]}",
                            }
                            for i in recent
                        ],
                    ),
                ],
            ),
        ]

    return ui.Stack(children=[
        ui.Header(text="SEO & Content", level=4),
        status_badges,
        ui.Divider(),
        nav,
        ui.Divider(),
        pipeline,
        ui.Divider(),
        new_btn,
        *([ui.Divider()] + recent_section_children if recent_section_children else []),
    ])

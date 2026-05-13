"""Left navigation sidebar."""
from __future__ import annotations

from imperal_sdk import ui

from wpb_app import ext, load_settings, load_ui_state, list_content, ser_ready, wp_ready, gsc_ready


def _nav_btn(label: str, view: str) -> ui.UINode:
    return ui.Button(label=label, on_click=ui.Call("__panel__editor", active_view=view, note_id="board"))


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

    # Show setup warning if not configured
    not_configured = not ser_ready(s) or not wp_ready(s)
    missing = []
    if not ser_ready(s): missing.append("SE Ranking")
    if not wp_ready(s):  missing.append("WordPress")

    status_badges = ui.Stack(children=[
        ui.Stack(children=[
            ui.Badge(label=f"SE Ranking {'✓' if ser_ready(s) else '— add key in Settings'}",
                     color="green" if ser_ready(s) else "orange"),
            ui.Badge(label=f"WordPress {'✓' if wp_ready(s) else '— add URL+password in Settings'}",
                     color="green" if wp_ready(s) else "orange"),
            ui.Badge(label=f"GSC {'✓' if gsc_ready(s) else '— add SA key in Settings'}",
                     color="green" if gsc_ready(s) else "gray"),
        ], gap=4),
        *([] if not not_configured else [
            ui.Alert(
                message=f"Setup needed: {', '.join(missing)}. Open ⚙️ Settings to connect.",
                type="warning",
            )
        ]),
    ])

    selected_id = state.get("selected_id")
    resume_btn_children = []
    if selected_id and active != "editor":
        open_item = next((i for i in items if i.get("id") == selected_id), None)
        label = (open_item.get("keyword") or open_item.get("title") or "item")[:28] if open_item else "item"
        resume_btn_children = [
            ui.Button(label=f"↩ Resume: {label}",
                      on_click=ui.Call("__panel__editor", active_view="editor", note_id="board")),
        ]

    def _nav_item(label: str, view: str, desc: str) -> ui.UINode:
        return ui.Stack(direction="v", gap=1, children=[
            ui.Button(label=label, on_click=ui.Call("__panel__editor", active_view=view, note_id="board")),
            ui.Text(content=desc, variant="caption"),
        ])

    nav = ui.Stack(children=[
        *resume_btn_children,
        _nav_item("📋 Content Plan",     "plan",
                  "AI article queue — gaps, keywords, growth topics"),
        _nav_item("📊 SEO Rankings",     "rankings",
                  "Google positions for your domain"),
        _nav_item("🔍 Keyword Research", "keywords",
                  "Find keywords by volume & difficulty"),
        _nav_item("📚 Brand Knowledge",  "docs",
                  "Upload brand docs — AI uses for writing style"),
        _nav_item("⚙️ Settings",         "settings",
                  "Connect SE Ranking, WordPress, brand info"),
    ], gap=4)

    pipeline = ui.Stack(children=[
        ui.Header(text="Article Pipeline", level=6),
        ui.Stack(children=[
            ui.Button(label=f"Ideas · {counts['idea']}",      on_click=ui.Call("__panel__editor", active_view="plan", plan_filter="idea",      note_id="board")),
            ui.Button(label=f"Writing · {counts['writing']}", on_click=ui.Call("__panel__editor", active_view="plan", plan_filter="writing",  note_id="board")),
            ui.Button(label=f"Review · {counts['review']}",   on_click=ui.Call("__panel__editor", active_view="plan", plan_filter="review",   note_id="board")),
            ui.Button(label=f"Done · {counts['published']}",  on_click=ui.Call("__panel__editor", active_view="plan", plan_filter="published", note_id="board")),
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

    STATUS_COLOR = {"idea": "gray", "writing": "blue", "review": "yellow", "published": "green"}

    recent_section_children = []
    if recent:
        total_words = sum(len((i.get("content") or "").split()) for i in items)
        published_count = counts["published"]
        recent_section_children = [
            ui.Header(text="Articles", level=6),
            ui.Text(
                content=f"{len(items)} total · {total_words:,} words · {published_count} published",
                variant="caption",
            ),
            ui.List(items=[
                ui.ListItem(
                    id=i["id"],
                    title=(i.get("keyword") or i.get("title") or "untitled")[:40],
                    subtitle=i.get("status", "idea"),
                    badge=ui.Badge(i.get("status", "idea"), color=STATUS_COLOR.get(i.get("status", "idea"), "gray")),
                    on_click=ui.Call("open_editor", content_id=i["id"]),
                )
                for i in recent
            ]),
        ]

    root = ui.Stack(children=[
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
    # Claim center slot on first load (Vikunja/Notes auto_action pattern).
    # Without this, ui.Call("__panel__editor", ...) from sidebar opens in right instead of center.
    root.props["auto_action"] = ui.Call("__panel__editor", note_id="board").to_dict()
    return root

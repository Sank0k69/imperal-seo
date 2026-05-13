"""Right panel — Article Info: details of the currently open content item."""
from __future__ import annotations

from imperal_sdk import ui

from wpb_app import ext, get_content, load_ui_state

REFRESH = (
    "on_event:seo.content.created,seo.content.updated,"
    "seo.content.deleted,seo.content.published,seo.nav.changed"
)

_STATUS_COLOR = {
    "idea": "gray", "writing": "blue", "review": "orange", "published": "green",
}


@ext.panel("article_info", slot="right", title="Article Info", icon="Info",
           default_width=260, refresh=REFRESH)
async def right_panel(ctx):
    state = await load_ui_state(ctx)
    cid = state.get("selected_id", "")

    if not cid:
        return ui.Empty(message="Open an article to see details.")

    item = await get_content(ctx, cid)
    if not item:
        return ui.Empty(message="Article not found.")

    keyword      = item.get("keyword", "—")
    title        = item.get("title") or keyword
    status       = item.get("status", "—")
    article_type = item.get("type", "—")
    volume       = str(item.get("volume") or "—")
    difficulty   = str(item.get("difficulty") or "—")
    priority     = item.get("priority") or "—"
    wp_post_id   = item.get("wp_post_id")
    target_url   = item.get("target_url", "")
    focus_kw     = item.get("focus_keyword") or keyword
    secondary    = item.get("secondary_keywords", [])
    meta_desc    = item.get("meta_description", "")
    generating   = item.get("generating", False)

    content_html = item.get("content", "")
    word_count   = len(content_html.split()) if content_html else 0

    overview_items = [
        {"key": "Keyword",  "value": keyword},
        {"key": "Type",     "value": article_type},
        {"key": "Priority", "value": str(priority)},
    ]
    if word_count:
        overview_items.append({"key": "Words", "value": str(word_count)})

    overview_children = [
        ui.Stack(direction="h", gap=2, align="center", children=[
            ui.Text(content="Status"),
            ui.Badge(label=status, color=_STATUS_COLOR.get(status, "gray")),
        ]),
        ui.KeyValue(items=overview_items),
    ]
    if generating:
        overview_children.append(ui.Alert(message="Generating...", type="info"))

    se_items = [
        {"key": "Volume",     "value": volume},
        {"key": "Difficulty", "value": difficulty},
        {"key": "Priority",   "value": str(priority)},
    ]

    if wp_post_id:
        wp_children = [
            ui.KeyValue(items=[{"key": "Post ID", "value": f"#{wp_post_id}"}]),
        ]
        if target_url:
            wp_children.append(
                ui.Button(
                    label="↗ View post",
                    variant="ghost",
                    size="sm",
                    on_click=ui.Navigate(target_url),
                )
            )
    else:
        wp_children = [ui.Text(content="Not published yet", variant="caption")]

    seo_items = [{"key": "Focus KW", "value": focus_kw}]
    if secondary:
        seo_items.append({"key": "Secondary", "value": ", ".join(secondary[:4])})
    if meta_desc:
        seo_items.append({"key": "Meta desc", "value": meta_desc[:100] + ("…" if len(meta_desc) > 100 else "")})

    title_display = title[:55] + ("…" if len(title) > 55 else "")

    return ui.Stack(gap=3, children=[
        ui.Header(text=title_display, level=4),
        ui.Section(title="Overview", collapsible=False, children=overview_children),
        ui.Section(title="SE Ranking", collapsible=True, children=[
            ui.KeyValue(items=se_items),
        ]),
        ui.Section(title="WordPress", collapsible=True, children=wp_children),
        ui.Section(title="SEO Meta", collapsible=True, children=[
            ui.KeyValue(items=seo_items),
        ]),
    ])

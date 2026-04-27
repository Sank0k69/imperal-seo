"""Editor view for content items — blog posts and newsletters.

Rendered by panels_workspace.py when active_view == 'editor'.
Newsletter mode: generate-from-news form + email-preview copy window.
Blog mode: RichEditor + WP publish.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import get_content

STATUS_COLOR = {
    "idea": "gray",
    "writing": "blue",
    "review": "yellow",
    "published": "green",
}


async def editor_view(ctx, state: dict) -> ui.UINode:
    content_id = state.get("selected_id")
    mode = state.get("editor_mode", "edit")

    if not content_id:
        return ui.Alert(message="No item selected. Go to Content Plan and open an item.", type="warning")

    item = await get_content(ctx, content_id)
    if not item:
        return ui.Alert(message=f"Item {content_id} not found.", type="error")

    item_type = item.get("type", "blog")

    if item_type == "newsletter":
        return _newsletter_editor(item, content_id, mode)
    return _blog_editor(item, content_id, mode)


# ── Newsletter editor ─────────────────────────────────────────────────────────

def _newsletter_editor(item: dict, content_id: str, mode: str) -> ui.UINode:
    kw = item.get("keyword", "")
    title = item.get("title", "")
    subject = item.get("subject", "")
    content_html = item.get("content", "")
    status = item.get("status", "idea")

    header = ui.Stack(children=[
        ui.Stack(children=[
            ui.Form(action="go_plan", submit_label="← Plan", children=[]),
            ui.Header(text=title or subject or kw, level=3),
            ui.Badge(label=status, color=STATUS_COLOR.get(status, "gray")),
            ui.Badge(label="newsletter", color="violet"),
        ], direction="horizontal", gap=8),
        ui.Stack(children=[
            ui.Form(
                action="set_editor_mode",
                submit_label="Preview" if mode == "edit" else "Edit",
                children=[ui.Input(param_name="mode", value="preview" if mode == "edit" else "edit")],
            ),
        ], direction="horizontal"),
    ], direction="horizontal", justify="between")

    # Generate-from-news form — always visible
    generate_form = ui.Section(
        title="Write newsletter from news",
        children=[
            ui.Form(
                action="generate_newsletter",
                submit_label="Generate newsletter →",
                children=[
                    ui.Input(param_name="content_id", value=content_id),
                    ui.TextArea(
                        param_name="news_text",
                        placeholder=(
                            "Paste the news, update, or topic here.\n\n"
                            "Example: 'We just launched HTTP/3 on all plans. "
                            "Tests show 2x faster page loads on mobile connections.'"
                        ),
                        rows=5,
                    ),
                    ui.Input(
                        param_name="tone_note",
                        placeholder="Tone note (optional) — e.g. 'more personal', 'focus on speed'",
                    ),
                ],
            ),
        ],
    )

    if not content_html:
        return ui.Stack(children=[
            header,
            ui.Divider(),
            generate_form,
            ui.Alert(
                message="Enter a news item above and click Generate — the newsletter will appear here ready to copy.",
                type="info",
            ),
        ])

    # Preview mode: email-style window + raw block for copying
    if mode == "preview":
        outer = "background:#e8e8e8;padding:32px;border-radius:10px;min-height:500px;"
        inner = (
            "max-width:620px;margin:0 auto;background:#fff;border-radius:8px;"
            "padding:40px 44px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "font-size:15px;line-height:1.75;color:#1a1a1a;box-shadow:0 2px 8px rgba(0,0,0,.10);"
        )
        meta_bar = (
            f'<div style="max-width:620px;margin:0 auto 8px;font-size:12px;color:#888;">'
            f'<strong>Subject:</strong> {subject or "—"}'
            f'</div>'
        )
        preview_html = (
            f'<div style="{outer}">'
            + meta_bar
            + f'<div style="{inner}">'
            + content_html
            + "</div></div>"
        )
        content_area = ui.Stack(children=[
            ui.Text(content="Email preview — select and copy text from below, or copy the HTML source from Edit mode", variant="caption"),
            ui.Html(content=preview_html),
        ])
    else:
        # Edit mode: editable RichEditor + save
        content_area = ui.Form(
            action="save_draft",
            submit_label="Save",
            children=[
                ui.Input(param_name="content_id", value=content_id),
                ui.Input(param_name="title", value=title, placeholder="Title"),
                ui.Input(param_name="subject", value=subject, placeholder="Email subject line"),
                ui.RichEditor(
                    param_name="content",
                    content=content_html,
                    placeholder="Newsletter body will appear here after generation.",
                ),
            ],
        )

    status_form = ui.Form(
        action="update_status",
        submit_label="Update status",
        children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Select(param_name="status", placeholder=f"Status: {status}", options=[
                {"value": "idea", "label": "Idea"},
                {"value": "writing", "label": "Writing"},
                {"value": "review", "label": "Review — ready to paste into MailerLite"},
                {"value": "published", "label": "Published / Sent"},
            ]),
        ],
    )

    copy_note = ui.Alert(
        message="Ready to send? Copy the text from preview, paste into MailerLite → create campaign → review → schedule.",
        type="info",
    )

    return ui.Stack(children=[
        header,
        ui.Divider(),
        generate_form,
        ui.Divider(),
        content_area,
        ui.Divider(),
        copy_note,
        status_form,
    ])


# ── Blog editor ───────────────────────────────────────────────────────────────

def _blog_editor(item: dict, content_id: str, mode: str) -> ui.UINode:
    kw = item.get("keyword", "")
    title = item.get("title", "")
    content_html = item.get("content", "")
    status = item.get("status", "idea")
    wp_id = item.get("wp_post_id")

    header = ui.Stack(children=[
        ui.Stack(children=[
            ui.Form(action="go_plan", submit_label="← Plan", children=[]),
            ui.Header(text=title or kw, level=3),
            ui.Badge(label=status, color=STATUS_COLOR.get(status, "gray")),
            ui.Badge(label="blog", color="blue"),
        ], direction="horizontal", gap=8),
        ui.Stack(children=[
            ui.Form(
                action="set_editor_mode",
                submit_label="Preview" if mode == "edit" else "Edit",
                children=[ui.Input(param_name="mode", value="preview" if mode == "edit" else "edit")],
            ),
        ], direction="horizontal"),
    ], direction="horizontal", justify="between")

    ai_bar = ui.Stack(children=[
        ui.Form(action="ai_brief", submit_label="AI Brief", children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Input(param_name="extra", placeholder="Extra context (optional)"),
        ]),
        ui.Form(action="ai_write", submit_label="AI Write", children=[
            ui.Input(param_name="content_id", value=content_id),
        ]),
        ui.Form(action="ai_write", submit_label="AI Improve", children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Input(param_name="section", value="improve"),
        ]),
    ], direction="horizontal", gap=8)

    if mode == "preview":
        outer = "background:#f5f5f5;padding:32px;border-radius:8px;min-height:480px;"
        inner = (
            "max-width:720px;margin:0 auto;background:#fff;border-radius:6px;"
            "padding:48px 52px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "font-size:16px;line-height:1.8;color:#1a1a1a;"
        )
        content_area = ui.Html(content=(
            f'<div style="{outer}"><div style="{inner}">'
            f'<h1 style="color:#111;margin-top:0;font-size:26px;">{title or kw}</h1>'
            + (content_html or "<p><em>No content. Switch to Edit mode.</em></p>")
            + "</div></div>"
        ))
    else:
        content_area = ui.Form(
            action="save_draft",
            submit_label="Save draft",
            children=[
                ui.Input(param_name="content_id", value=content_id),
                ui.Input(param_name="title", value=title, placeholder="Title (H1)"),
                ui.RichEditor(
                    param_name="content",
                    content=content_html,
                    placeholder="Start writing or use AI Brief → AI Write above...",
                ),
            ],
        )

    publish_bar = ui.Stack(children=[
        ui.Form(action="publish_wp", submit_label="→ WP Draft", children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Input(param_name="status", value="draft"),
        ]),
        ui.Form(action="publish_wp", submit_label="→ Publish on WordPress", children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Input(param_name="status", value="publish"),
        ]),
        *(
            [ui.Badge(label=f"WP #{wp_id} — {item.get('target_url', '')[:40]}", color="green")]
            if wp_id else []
        ),
    ], direction="horizontal", gap=8)

    meta = ui.KeyValue(items=[
        {"key": "Keyword", "value": kw},
        {"key": "Volume", "value": f"{item.get('volume', 0):,}/mo"},
        {"key": "Difficulty", "value": f"{item.get('difficulty', '—')}/100"},
    ])

    status_form = ui.Form(
        action="update_status",
        submit_label="Update status",
        children=[
            ui.Input(param_name="content_id", value=content_id),
            ui.Select(param_name="status", placeholder=f"Status: {status}", options=[
                {"value": "idea", "label": "Idea"},
                {"value": "writing", "label": "Writing"},
                {"value": "review", "label": "Review"},
                {"value": "published", "label": "Published"},
            ]),
        ],
    )

    return ui.Stack(children=[
        header,
        ui.Divider(),
        ai_bar,
        ui.Divider(),
        content_area,
        ui.Divider(),
        meta,
        status_form,
        ui.Divider(),
        publish_bar,
    ])

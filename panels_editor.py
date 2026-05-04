"""Editor view — clean step-by-step UX. All handlers read content_id from UI state."""
from __future__ import annotations

from imperal_sdk import ui

from app import get_content, load_settings

STATUS_COLOR = {
    "idea":      "gray",
    "writing":   "blue",
    "review":    "yellow",
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

    if item.get("type") == "newsletter":
        return _newsletter_editor(item, mode)

    s = await load_settings(ctx)
    wp_base_url = s.get("wp_url", "").rstrip("/")
    return _blog_editor(item, mode, wp_base_url)


# ── Blog editor ───────────────────────────────────────────────────────────────

def _blog_editor(item: dict, mode: str, wp_base_url: str = "") -> ui.UINode:
    kw           = item.get("keyword", "")
    title        = item.get("title", "")
    content_html = item.get("content", "")
    brief_text   = item.get("brief", "")
    status       = item.get("status", "idea")
    wp_id        = item.get("wp_post_id")
    wp_url       = item.get("target_url", "")
    meta_desc    = item.get("meta_description", "")
    focus_kw     = item.get("focus_keyword", "") or kw

    has_content = bool(content_html and len(content_html.strip()) > 100)

    # ── Header ────────────────────────────────────────────────────────────────
    toggle_btn = ui.Form(action="go_preview", submit_label="Preview", children=[]) \
        if mode == "edit" else \
        ui.Form(action="go_edit", submit_label="← Edit", children=[])

    header = ui.Stack(children=[
        ui.Stack(children=[
            ui.Form(action="go_plan", submit_label="← Plan", children=[]),
            ui.Header(text=title or kw, level=3),
            ui.Badge(label=status, color=STATUS_COLOR.get(status, "gray")),
        ], direction="horizontal", gap=8),
        toggle_btn,
    ], direction="horizontal", justify="between")

    meta = ui.Stack(children=[
        ui.Text(content=f"Keyword: {kw}  ·  Volume: {item.get('volume', 0):,}/mo  ·  Difficulty: {item.get('difficulty', '—')}/100", variant="caption"),
    ])

    # ── Step 1: AI Brief ──────────────────────────────────────────────────────
    step1_children = [
        ui.Text(content="AI builds an SEO outline: title, meta description, H2/H3 structure, search intent.", variant="caption"),
        ui.Form(
            action="generate_brief",
            submit_label="Generate Brief",
            children=[
                ui.Input(param_name="extra", placeholder="Extra context (optional) — e.g. 'focus on VPS for developers'"),
            ],
        ),
    ]
    if brief_text:
        step1_children += [
            ui.Divider(),
            ui.Text(content="Brief ready — used as context when writing the article:", variant="caption"),
            ui.Markdown(content=brief_text[:1200] + ("..." if len(brief_text) > 1200 else "")),
            ui.Form(
                action="save_brief",
                submit_label="Save edited brief",
                children=[
                    ui.TextArea(param_name="brief_text", value=brief_text, rows=12),
                ],
            ),
            ui.Form(action="generate_brief", submit_label="Regenerate Brief", children=[]),
        ]
    step1 = ui.Section(
        title=f"Step 1 — Brief {'✓' if brief_text else '(optional)'}",
        children=step1_children,
    )

    # ── Step 2: AI Write ──────────────────────────────────────────────────────
    article_type = item.get("type", "blog")
    generating   = item.get("generating", False)
    type_options = [
        {"value": "blog",       "label": "Blog post (informational)"},
        {"value": "comparison", "label": "Comparison / X vs Y"},
        {"value": "tutorial",   "label": "Tutorial / step-by-step"},
        {"value": "pillar",     "label": "Pillar page (comprehensive)"},
        {"value": "news",       "label": "News / announcement"},
        {"value": "review",     "label": "Product / service review"},
    ]

    if generating:
        step2 = ui.Section(
            title="Step 2 — Writing article...",
            children=[
                ui.Loading(),
                ui.Text(content="Generation takes ~60-90 seconds. Click below to check.", variant="caption"),
                ui.Form(action="check_article_job", submit_label="Check result →", children=[]),
            ],
        )
    else:
        step2_children = [
            ui.Text(content="AI writes the full article. Run Brief first for better results.", variant="caption"),
            ui.Form(
                action="ai_write",
                submit_label="Write Full Article",
                children=[
                    ui.Select(
                        param_name="article_type",
                        placeholder=f"Article type: {article_type}",
                        options=type_options,
                    ),
                ],
            ),
        ]
        if has_content:
            step2_children.append(
                ui.Form(action="ai_write", submit_label="Improve Article",
                        children=[ui.Input(param_name="section", value="improve")])
            )
        step2 = ui.Section(title="Step 2 — Write with AI", children=step2_children)

    # ── Step 3: Editor ────────────────────────────────────────────────────────
    if mode == "preview":
        outer = "background:#f5f5f5;padding:32px;border-radius:8px;"
        inner = (
            "max-width:720px;margin:0 auto;background:#fff;border-radius:6px;"
            "padding:48px 52px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "font-size:16px;line-height:1.8;color:#1a1a1a;"
        )
        step3 = ui.Html(content=(
            f'<div style="{outer}"><div style="{inner}">'
            f'<h1 style="color:#111;margin-top:0;font-size:26px;">{title or kw}</h1>'
            + (content_html or "<p><em>No content yet — run AI Write.</em></p>")
            + "</div></div>"
        ))
    else:
        step3 = ui.Section(
            title="Step 3 — Edit & Save",
            children=[
                ui.Form(
                    action="save_draft",
                    submit_label="Save",
                    children=[
                        ui.Input(param_name="title", value=title, placeholder="Article title (H1)"),
                        ui.RichEditor(
                            param_name="content",
                            content=content_html,
                            placeholder="Run AI Write above, or start typing here...",
                        ),
                    ],
                ),
            ],
        )

    # ── Step 4: Publish ───────────────────────────────────────────────────────
    seo_done = bool(item.get("meta_description") or item.get("excerpt"))
    wp_admin_link = f"{wp_base_url}/wp-admin/post.php?post={wp_id}&action=edit" if wp_base_url and wp_id else ""

    if wp_id:
        link_parts = []
        if wp_url:
            link_parts.append(f'<a href="{wp_url}" target="_blank" style="font-size:12px;color:#0073aa;text-decoration:none;">↗ View post</a>')
        if wp_admin_link:
            link_parts.append(f'<a href="{wp_admin_link}" target="_blank" style="font-size:12px;color:#555;text-decoration:none;">✏ Edit in WP Admin</a>')

        publish_section = ui.Section(
            title=f"Step 4 — Published (WP #{wp_id})",
            children=[
                ui.Stack(children=[
                    ui.Badge(label=f"WP #{wp_id}", color="green"),
                    ui.Badge(
                        label="Rank Math ✓" if seo_done else "Rank Math not set",
                        color="green" if seo_done else "orange",
                    ),
                ], direction="horizontal", gap=8),
                *([ ui.Html(content=f'<div style="display:flex;gap:16px;margin:4px 0;">{"  ".join(link_parts)}</div>') ] if link_parts else []),
                ui.Stack(children=[
                    ui.Form(action="publish_wp_draft",   submit_label="Update WP Post",   children=[]),
                    ui.Form(action="publish_wp_publish", submit_label="Set as Published", children=[]),
                ], direction="horizontal", gap=8),
                ui.Divider(),
                ui.Header(text="SEO Meta (Rank Math)", level=5),
                ui.Text(content="Sets focus + secondary keywords, meta description, excerpt. All auto-generated if left empty.", variant="caption"),
                ui.Form(
                    action="set_wp_seo",
                    submit_label="Set SEO Meta",
                    children=[
                        ui.Input(param_name="focus_keyword",    value=focus_kw,   placeholder=f"Focus keyword (default: {kw})"),
                        ui.Input(param_name="meta_description", value=meta_desc,  placeholder="Meta description (leave empty — AI generates)"),
                    ],
                ),
            ],
            collapsible=True,
            )
    else:
        publish_section = ui.Section(
            title="Step 4 — Publish to WordPress",
            children=[
                ui.Text(
                    content="Publishes as draft — you can review in WP before going live.",
                    variant="caption",
                ),
                ui.Stack(children=[
                    ui.Form(action="publish_wp_draft",   submit_label="→ Save as WP Draft", children=[]),
                    ui.Form(action="publish_wp_publish", submit_label="→ Publish Now",      children=[]),
                ], direction="horizontal", gap=8),
            ],
        )

    status_section = ui.Section(
        title=f"Status: {status}",
        collapsible=True,
        children=[
            ui.Text(content="Statuses update automatically. Use only if you need to override.", variant="caption"),
            ui.Form(
                action="update_status",
                submit_label="Set status",
                children=[
                    ui.Select(param_name="status", placeholder=f"Current: {status}", options=[
                        {"value": "idea",      "label": "Idea"},
                        {"value": "writing",   "label": "Writing"},
                        {"value": "review",    "label": "Review"},
                        {"value": "published", "label": "Published"},
                    ]),
                ],
            ),
        ],
    )

    return ui.Stack(children=[
        header,
        meta,
        ui.Divider(),
        step1,
        step2,
        ui.Divider(),
        step3,
        ui.Divider(),
        publish_section,
        ui.Divider(),
        status_section,
    ])


# ── Newsletter editor ─────────────────────────────────────────────────────────

def _newsletter_editor(item: dict, mode: str) -> ui.UINode:
    kw           = item.get("keyword", "")
    title        = item.get("title", "")
    subject      = item.get("subject", "")
    content_html = item.get("content", "")
    status       = item.get("status", "idea")

    nl_toggle = ui.Form(action="go_preview", submit_label="Preview", children=[]) \
        if mode == "edit" else \
        ui.Form(action="go_edit", submit_label="← Edit", children=[])

    header = ui.Stack(children=[
        ui.Stack(children=[
            ui.Form(action="go_plan", submit_label="← Plan", children=[]),
            ui.Header(text=title or subject or kw, level=3),
            ui.Badge(label=status, color=STATUS_COLOR.get(status, "gray")),
            ui.Badge(label="newsletter", color="violet"),
        ], direction="horizontal", gap=8),
        nl_toggle,
    ], direction="horizontal", justify="between")

    generate_form = ui.Section(
        title="Generate newsletter from news",
        children=[
            ui.Form(
                action="generate_newsletter",
                submit_label="Generate newsletter →",
                children=[
                    ui.TextArea(
                        param_name="news_text",
                        placeholder="Paste the news, update, or topic here...",
                        rows=5,
                    ),
                    ui.Input(param_name="tone_note", placeholder="Tone note (optional)"),
                ],
            ),
        ],
    )

    if not content_html:
        return ui.Stack(children=[
            header,
            ui.Divider(),
            generate_form,
            ui.Alert(message="Enter a topic above and click Generate.", type="info"),
        ])

    if mode == "preview":
        outer = "background:#e8e8e8;padding:32px;border-radius:10px;"
        inner = (
            "max-width:620px;margin:0 auto;background:#fff;border-radius:8px;"
            "padding:40px 44px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "font-size:15px;line-height:1.75;color:#1a1a1a;"
        )
        meta_bar = f'<div style="max-width:620px;margin:0 auto 8px;font-size:12px;color:#888;"><strong>Subject:</strong> {subject or "—"}</div>'
        content_area = ui.Stack(children=[
            ui.Text(content="Email preview — copy text or switch to Edit to get raw HTML", variant="caption"),
            ui.Html(content=f'<div style="{outer}">{meta_bar}<div style="{inner}">{content_html}</div></div>'),
        ])
    else:
        content_area = ui.Form(
            action="save_draft",
            submit_label="Save",
            children=[
                ui.Input(param_name="title",   value=title,   placeholder="Title"),
                ui.Input(param_name="subject", value=subject, placeholder="Email subject line"),
                ui.RichEditor(param_name="content", content=content_html, placeholder="Newsletter body"),
            ],
        )

    status_form = ui.Form(
        action="update_status",
        submit_label="Update status",
        children=[
            ui.Select(param_name="status", placeholder=f"Status: {status}", options=[
                {"value": "idea",      "label": "Idea"},
                {"value": "writing",   "label": "Writing"},
                {"value": "review",    "label": "Review — ready to paste into MailerLite"},
                {"value": "published", "label": "Published / Sent"},
            ]),
        ],
    )

    return ui.Stack(children=[
        header,
        ui.Divider(),
        generate_form,
        ui.Divider(),
        content_area,
        ui.Divider(),
        ui.Alert(message="Ready? Copy from Preview → paste into MailerLite → schedule.", type="info"),
        status_form,
    ])

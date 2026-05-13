"""Settings view — Brand, SE Ranking, WordPress in separate forms."""
from __future__ import annotations

from imperal_sdk import ui

from wpb_app import load_settings


def _masked(v: str) -> str:
    if not v:
        return ""
    return "••••" + v[-4:] if len(v) > 8 else "••••"


async def _settings_view(ctx) -> ui.UINode:
    s = await load_settings(ctx)

    # ── Blog Writing Style ────────────────────────────────────────────────────
    blog_url = s.get("blog_url", "")
    active_profile = s.get("active_profile", "")
    blog_style_section = ui.Section(
        title="Blog Writing Style",
        children=[
            ui.Text(
                content=(
                    "Analyze your existing blog to automatically configure the AI writer to match your style. "
                    "The AI will crawl your RSS feed, read 5 recent posts, and create a custom writing profile."
                ),
                variant="caption",
            ),
            ui.Form(
                action="setup_blog_style",
                submit_label="Analyze my blog & set style",
                children=[
                    ui.Input(
                        param_name="blog_url",
                        value=blog_url,
                        placeholder="https://blog.yourdomain.com",
                    ),
                ],
            ),
            *([] if not active_profile else [
                ui.Alert(message=f"Active writing profile: {active_profile}", type="info"),
            ]),
        ],
    )

    # ── Brand & Newsletter ─────────────────────────────────────────────────────
    brand_form = ui.Form(
        action="save_settings",
        submit_label="Save Brand & Newsletter",
        children=[
            ui.Input(param_name="company_name",
                     value=s.get("company_name", ""),
                     placeholder="Company name — e.g. WebHostMost"),
            ui.TextArea(param_name="brand_description",
                        value=s.get("brand_description", ""),
                        placeholder="What your company does (1-2 sentences).",
                        rows=2),
            ui.TextArea(param_name="brand_voice",
                        value=s.get("brand_voice", ""),
                        placeholder="Voice instruction — e.g. 'Direct and bold. Short sentences.'",
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
        ],
    )

    # ── SE Ranking ────────────────────────────────────────────────────────────
    ser_form = ui.Form(
        action="save_settings",
        submit_label="Save SE Ranking",
        children=[
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
            ui.Input(param_name="seranking_competitor",
                     value=s.get("seranking_competitor", ""),
                     placeholder="Competitor domain for gap analysis — e.g. hostinger.com"),
        ],
    )

    # ── WordPress ─────────────────────────────────────────────────────────────
    wp_form = ui.Form(
        action="save_settings",
        submit_label="Save WordPress",
        children=[
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

    # ── Google Search Console ──────────────────────────────────────────────────
    gsc_form = ui.Form(
        action="save_settings",
        submit_label="Save GSC",
        children=[
            ui.Text(
                content="Create a Service Account in Google Cloud → enable Search Console API → "
                        "add the SA email as User in GSC property → paste JSON here.",
                variant="caption",
            ),
            ui.Input(
                param_name="gsc_site_url",
                value=s.get("gsc_site_url", ""),
                placeholder="GSC property URL — https://webhostmost.com or sc-domain:webhostmost.com",
            ),
            ui.TextArea(
                param_name="gsc_service_account",
                placeholder=f"Service Account JSON{' (set ✓)' if s.get('gsc_service_account') else ' — paste full JSON from Google Cloud'}",
                rows=3,
            ),
        ],
    )

    return ui.Stack(children=[
        ui.Stack(children=[
            ui.Header(text="Settings", level=3),
            ui.Button(label="← Back", on_click=ui.Call("__panel__editor", active_view="plan", note_id="board")),
        ], direction="horizontal", justify="between"),
        ui.Alert(message="API keys stored encrypted per user.", type="info"),
        blog_style_section,
        ui.Divider(),
        ui.Section(title="Brand & Newsletter", collapsible=False, children=[brand_form]),
        ui.Divider(),
        ui.Section(title="SE Ranking", collapsible=True, children=[ser_form]),
        ui.Divider(),
        ui.Section(title="WordPress", collapsible=True, children=[wp_form]),
        ui.Divider(),
        ui.Section(title="Google Search Console", collapsible=True, children=[gsc_form]),
    ])

"""Secrets/right panel — registered to satisfy platform panel registry."""
from imperal_sdk import ui
from wpb_app import ext


@ext.panel("secrets", slot="right", title="Settings", icon="Settings", default_width=280)
async def secrets_panel(ctx, **_kw):
    """Right panel — shows connection status."""
    return ui.Empty(message="")

"""Hot-reload entry point — imports register all decorators."""
from __future__ import annotations

import sys
import os
import importlib.util

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

# Force-register OUR api_client from absolute path before any imports.
# This prevents shared Python env from picking up another extension's api_client.
_ac_spec = importlib.util.spec_from_file_location("api_client", os.path.join(_dir, "api_client.py"))
_ac_mod = importlib.util.module_from_spec(_ac_spec)
_ac_spec.loader.exec_module(_ac_mod)
sys.modules["api_client"] = _ac_mod

for _m in list(sys.modules):
    if _m in (
        "wpb_app", "params", "api_seranking", "api_wordpress",
        "handlers_nav", "handlers_content", "handlers_ai_write", "handlers_ai_extra",
        "handlers_seo", "handlers_publish", "handlers_docs", "handlers_keywords",
        "panels_side", "panels_right", "panels_article_info", "panels_workspace",
        "panels_editor", "panels_editor_helpers", "panels_editor_newsletter",
        "panels_settings_view", "panels_docs", "skeleton",
    ):
        del sys.modules[_m]

from wpb_app import ext, chat  # noqa: E402, F401

import handlers_nav        # noqa: E402, F401
import handlers_content    # noqa: E402, F401
import handlers_ai_write   # noqa: E402, F401
import handlers_ai_extra   # noqa: E402, F401
import handlers_seo        # noqa: E402, F401
import handlers_publish    # noqa: E402, F401
import handlers_docs       # noqa: E402, F401
import handlers_keywords   # noqa: E402, F401
import skeleton            # noqa: E402, F401
import panels_side         # noqa: E402, F401
import panels_article_info # noqa: E402, F401
import panels_workspace    # noqa: E402, F401

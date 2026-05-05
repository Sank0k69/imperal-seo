"""Hot-reload entry point — imports register all decorators."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in (
        "app", "params", "api_client", "api_seranking", "api_wordpress",
        "handlers_nav", "handlers_content", "handlers_seo",
        "handlers_publish", "handlers_docs",
        "panels_side", "panels_workspace", "panels_editor", "panels_docs",
        "panels_right",
    ):
        del sys.modules[_m]

from app import ext, chat  # noqa: E402, F401

import handlers_nav      # noqa: E402, F401
import handlers_content  # noqa: E402, F401
import handlers_seo      # noqa: E402, F401
import handlers_publish  # noqa: E402, F401
import handlers_docs     # noqa: E402, F401
import panels_side       # noqa: E402, F401
import panels_workspace  # noqa: E402, F401
import panels_right      # noqa: E402, F401

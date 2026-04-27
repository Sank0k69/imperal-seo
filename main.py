"""Hot-reload entry point — imports register all decorators."""
from app import ext, chat  # noqa: F401
import handlers_nav      # noqa: F401
import handlers_content  # noqa: F401
import handlers_seo      # noqa: F401
import handlers_publish  # noqa: F401
import handlers_docs     # noqa: F401
import panels_side       # noqa: F401
import panels_workspace  # noqa: F401
import panels_docs       # noqa: F401

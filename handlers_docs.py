"""Knowledge base handlers — upload, list, delete documentation files."""
import base64

from imperal_sdk import ActionResult
from imperal_sdk.types import ActionResult  # noqa: F811

from app import chat, ext
from params import DeleteDocParams, EmptyParams, UploadDocParams

DOCS_COLLECTION = "seo_docs"
MAX_CONTEXT_CHARS = 3000  # per doc, for AI injection


@chat.function(
    "upload_doc",
    description="Upload a documentation file (.md or .txt) to the knowledge base. Used as AI context when writing content.",
    action_type="write",
    event="seo.docs.updated",
)
async def upload_doc(ctx, params: UploadDocParams) -> ActionResult:
    """Receive base64 file(s) from FileUpload, decode and store as knowledge base docs."""
    raw_files = getattr(params, "files", None) or []
    if not raw_files:
        return ActionResult.error(error="No files received.")

    if isinstance(raw_files, str):
        raw_files = [raw_files]

    saved = []
    for f in raw_files:
        if isinstance(f, dict):
            name = f.get("name", "doc.md")
            b64 = f.get("content", "")
            size = f.get("size", 0)
        else:
            name = "doc.md"
            b64 = str(f)
            size = 0

        try:
            text = base64.b64decode(b64).decode("utf-8", errors="replace")
        except Exception:
            text = str(b64)

        ext_lower = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext_lower not in ("md", "txt", "markdown"):
            continue

        doc_data = {
            "name": name,
            "content": text[:12000],
            "size": size or len(text),
            "ext": ext_lower,
        }

        page = await ctx.store.query(DOCS_COLLECTION, limit=50)
        docs = getattr(page, "data", None) or []
        existing = next((d for d in docs if getattr(d, "data", {}).get("name") == name), None)
        if existing:
            await ctx.store.update(DOCS_COLLECTION, existing.id, doc_data)
        else:
            await ctx.store.create(DOCS_COLLECTION, doc_data)

        saved.append(name)

    if not saved:
        return ActionResult.error(error="No valid .md or .txt files found in the upload.")

    return ActionResult.success(
        {"saved": saved},
        summary=f"Uploaded {len(saved)} doc(s): {', '.join(saved)}",
    )


@chat.function(
    "delete_doc",
    description="Delete a documentation file from the knowledge base.",
    action_type="write",
    event="seo.docs.updated",
)
async def delete_doc(ctx, params: DeleteDocParams) -> ActionResult:
    """Remove a doc from the knowledge base by store ID."""
    try:
        await ctx.store.delete(DOCS_COLLECTION, params.doc_id)
    except Exception as e:
        return ActionResult.error(error=f"Could not delete doc: {e}")
    return ActionResult.success({"id": params.doc_id}, summary="Doc deleted")


@chat.function(
    "list_docs",
    description="List all uploaded documentation files in the knowledge base.",
    action_type="read",
)
async def list_docs_fn(ctx, params: EmptyParams) -> ActionResult:
    """Return all docs in the knowledge base."""
    docs = await _load_docs(ctx)
    summary_lines = [f"• {d['name']} ({d.get('size', 0)} chars)" for d in docs]
    return ActionResult.success(
        {"docs": docs, "count": len(docs)},
        summary=f"{len(docs)} doc(s) in knowledge base:\n" + "\n".join(summary_lines),
    )


async def _load_docs(ctx) -> list[dict]:
    try:
        page = await ctx.store.query(DOCS_COLLECTION, limit=20)
    except Exception:
        return []
    docs = getattr(page, "data", None) or []
    result = []
    for d in docs:
        if isinstance(getattr(d, "data", None), dict):
            item = dict(d.data)
            item["id"] = d.id
            result.append(item)
    return result


async def build_docs_context(ctx) -> str:
    """Load all docs and return a single context string for AI prompts."""
    docs = await _load_docs(ctx)
    if not docs:
        return ""
    parts = []
    for doc in docs:
        content = (doc.get("content") or "")[:MAX_CONTEXT_CHARS]
        parts.append(f"=== {doc['name']} ===\n{content}")
    return "\n\n".join(parts)

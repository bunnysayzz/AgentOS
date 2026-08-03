"""Prompt Registry service - CRUD, version management, template rendering (Firestore)."""

import re

from app.core.db import FirestoreDB, now_iso, stamp
from app.schemas.prompt import PromptCreate, PromptUpdate, PromptVersionCreate

PROMPTS = "prompts"
PROMPT_VERSIONS = "prompt_versions"


# ─── Errors ──────────────────────────────────────────


class PromptError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class PromptNotFoundError(PromptError):
    def __init__(self):
        super().__init__("Prompt not found", status_code=404)


class VersionNotFoundError(PromptError):
    def __init__(self):
        super().__init__("Version not found", status_code=404)


class PromptSlugTakenError(PromptError):
    def __init__(self):
        super().__init__("A prompt with this slug already exists", status_code=409)


def _slug_taken(db: FirestoreDB, slug: str, workspace_id: str | None) -> bool:
    rows = db.query(PROMPTS) if workspace_id is None else db.query(PROMPTS, "workspace_id", str(workspace_id))
    for row in rows:
        if row.get("slug") == slug and not row.get("deleted_at"):
            return True
    return False


# ─── Prompt CRUD ────────────────────────────────────


async def create_prompt(db: FirestoreDB, prompt_in: PromptCreate, workspace_id: str | None = None) -> dict:
    """Create a new prompt with an initial version."""
    slug = prompt_in.slug
    if slug is None:
        slug = prompt_in.name.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = "prompt"

    if _slug_taken(db, slug, workspace_id):
        raise PromptSlugTakenError()

    prompt = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "name": prompt_in.name,
        "slug": slug,
        "description": prompt_in.description,
        "prompt_type": prompt_in.prompt_type.value,
        "is_public": prompt_in.is_public,
        "tags": prompt_in.tags,
        "current_version": 0,
    })
    db.add(PROMPTS, prompt)

    content = prompt_in.initial_content or ""
    await _add_version(db, prompt, PromptVersionCreate(content=content, commit_message="Initial version"))
    return prompt


async def get_prompt_by_id(db: FirestoreDB, prompt_id: str) -> dict | None:
    """Get a prompt by ID."""
    prompt = db.get(PROMPTS, str(prompt_id))
    if prompt is None or prompt.get("deleted_at"):
        return None
    return prompt


async def list_workspace_prompts(
    db: FirestoreDB, workspace_id: str | None, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List prompts available to a workspace."""
    rows = [r for r in db.query(PROMPTS) if not r.get("deleted_at")]
    if workspace_id:
        rows = [r for r in rows if str(r.get("workspace_id") or "") == str(workspace_id)]
    else:
        rows = [r for r in rows if r.get("is_public")]
    rows.sort(key=lambda r: (r.get("updated_at") or "", r.get("created_at") or ""), reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def update_prompt(db: FirestoreDB, prompt: dict, prompt_in: PromptUpdate) -> dict:
    """Update a prompt's metadata."""
    update_data = prompt_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        prompt[field] = value
    db.set(PROMPTS, prompt["id"], prompt)
    return prompt


async def delete_prompt(db: FirestoreDB, prompt: dict) -> None:
    """Soft-delete a prompt."""
    prompt["deleted_at"] = now_iso()
    db.set(PROMPTS, prompt["id"], prompt)


# ─── Version Management ─────────────────────────────


async def _add_version(db: FirestoreDB, prompt: dict, version_in: PromptVersionCreate) -> dict:
    """Add a new version to a prompt (internal helper)."""
    next_version = (prompt.get("current_version") or 0) + 1

    char_count = len(version_in.content)
    token_count = char_count // 4

    version = stamp({
        "prompt_id": prompt["id"],
        "version": next_version,
        "content": version_in.content,
        "template_variables": version_in.template_variables or _extract_variables(version_in.content),
        "commit_message": version_in.commit_message or f"Version {next_version}",
        "token_count": token_count,
        "char_count": char_count,
    })
    db.add(PROMPT_VERSIONS, version)

    prompt["current_version"] = next_version
    db.set(PROMPTS, prompt["id"], prompt)
    return version


async def create_version(db: FirestoreDB, prompt: dict, version_in: PromptVersionCreate) -> dict:
    """Create a new version of a prompt."""
    return await _add_version(db, prompt, version_in)


async def get_version(db: FirestoreDB, prompt_id: str, version: int) -> dict | None:
    """Get a specific version of a prompt."""
    for row in db.query(PROMPT_VERSIONS, "prompt_id", str(prompt_id)):
        if row.get("version") == version:
            return row
    return None


async def get_current_version(db: FirestoreDB, prompt: dict) -> dict | None:
    """Get the current (latest) version of a prompt."""
    return await get_version(db, prompt["id"], prompt.get("current_version") or 0)


async def list_versions(
    db: FirestoreDB, prompt_id: str, page: int = 1, page_size: int = 50
) -> tuple[list[dict], int]:
    """List all versions of a prompt."""
    rows = db.query(PROMPT_VERSIONS, "prompt_id", str(prompt_id))
    rows.sort(key=lambda r: r.get("version") or 0, reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def rollback_to_version(db: FirestoreDB, prompt: dict, target_version: int) -> dict:
    """Rollback a prompt to a previous version by creating a new version."""
    target = await get_version(db, prompt["id"], target_version)
    if target is None:
        raise VersionNotFoundError()

    return await _add_version(
        db, prompt,
        PromptVersionCreate(
            content=target["content"],
            template_variables=target.get("template_variables"),
            commit_message=f"Rollback to version {target_version}",
        ),
    )


# ─── Template Rendering ─────────────────────────────


def _extract_variables(template: str) -> list[str]:
    """Extract template variable names from a template string."""
    variables = set()
    for match in re.finditer(r"\{\{\s*(\w+)\s*\}\}", template):
        variables.add(match.group(1))
    for match in re.finditer(r"(?<!\{)\{(\w+)\}(?!\})", template):
        variables.add(match.group(1))
    return sorted(variables)


async def render_prompt(
    db: FirestoreDB, prompt: dict, variables: dict[str, str] | None = None,
    version: int | None = None,
) -> str:
    """Render a prompt template with variables."""
    if version is not None:
        ver = await get_version(db, prompt["id"], version)
    else:
        ver = await get_current_version(db, prompt)

    if ver is None:
        raise VersionNotFoundError()

    content = ver["content"]
    if variables:
        for key in sorted(variables.keys(), key=len, reverse=True):
            value = variables[key]
            content = content.replace("{{" + key + "}}", value)
            content = content.replace("{{ " + key + " }}", value)
            content = content.replace("{" + key + "}", value)

    return content

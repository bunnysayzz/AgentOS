"""Prompt Registry service - CRUD, version management, template rendering."""

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt import Prompt, PromptVersion, PromptType
from app.schemas.prompt import PromptCreate, PromptUpdate, PromptVersionCreate


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


# ─── Prompt CRUD ────────────────────────────────────


async def create_prompt(db: AsyncSession, prompt_in: PromptCreate, workspace_id: UUID | None = None) -> Prompt:
    """Create a new prompt with an initial version."""
    # Auto-generate slug from name if not provided
    slug = prompt_in.slug
    if slug is None:
        slug = prompt_in.name.lower().replace(" ", "_").replace("-", "_")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            slug = "prompt"

    # Check slug uniqueness within workspace
    result = await db.execute(
        select(Prompt).where(
            Prompt.slug == slug,
            Prompt.workspace_id == workspace_id,
            Prompt.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise PromptSlugTakenError()

    prompt = Prompt(
        workspace_id=workspace_id,
        name=prompt_in.name,
        slug=slug,
        description=prompt_in.description,
        prompt_type=prompt_in.prompt_type,
        is_public=prompt_in.is_public,
        tags=prompt_in.tags,
        current_version=0,
    )
    db.add(prompt)
    await db.flush()

    # Create the initial version (always, even if empty)
    content = prompt_in.initial_content or ""
    await _add_version(db, prompt, PromptVersionCreate(
        content=content,
        commit_message="Initial version",
    ))

    await db.refresh(prompt)
    return prompt


async def get_prompt_by_id(db: AsyncSession, prompt_id: UUID) -> Prompt | None:
    """Get a prompt by ID."""
    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id, Prompt.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def list_workspace_prompts(
    db: AsyncSession, workspace_id: UUID | None, page: int = 1, page_size: int = 50
) -> tuple[list[Prompt], int]:
    """List prompts available to a workspace."""
    offset = (page - 1) * page_size

    conditions = [Prompt.deleted_at.is_(None)]
    if workspace_id:
        conditions.append(Prompt.workspace_id == workspace_id)
    else:
        conditions.append(Prompt.is_public.is_(True))

    count_result = await db.execute(select(func.count(Prompt.id)).where(*conditions))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Prompt)
        .where(*conditions)
        .order_by(Prompt.updated_at.desc().nulls_last(), Prompt.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def update_prompt(db: AsyncSession, prompt: Prompt, prompt_in: PromptUpdate) -> Prompt:
    """Update a prompt's metadata."""
    update_data = prompt_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prompt, field, value)
    await db.flush()
    await db.refresh(prompt)
    return prompt


async def delete_prompt(db: AsyncSession, prompt: Prompt) -> None:
    """Soft-delete a prompt."""
    prompt.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ─── Version Management ─────────────────────────────


async def _add_version(
    db: AsyncSession, prompt: Prompt, version_in: PromptVersionCreate
) -> PromptVersion:
    """Add a new version to a prompt (internal helper)."""
    next_version = prompt.current_version + 1

    # Count tokens approximately (4 chars ~= 1 token)
    char_count = len(version_in.content)
    token_count = char_count // 4

    version = PromptVersion(
        prompt_id=prompt.id,
        version=next_version,
        content=version_in.content,
        template_variables=version_in.template_variables or _extract_variables(version_in.content),
        commit_message=version_in.commit_message or f"Version {next_version}",
        token_count=token_count,
        char_count=char_count,
    )
    db.add(version)
    prompt.current_version = next_version
    await db.flush()
    await db.refresh(version)
    return version


async def create_version(
    db: AsyncSession, prompt: Prompt, version_in: PromptVersionCreate
) -> PromptVersion:
    """Create a new version of a prompt."""
    return await _add_version(db, prompt, version_in)


async def get_version(
    db: AsyncSession, prompt_id: UUID, version: int
) -> PromptVersion | None:
    """Get a specific version of a prompt."""
    result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version == version,
        )
    )
    return result.scalar_one_or_none()


async def get_current_version(db: AsyncSession, prompt: Prompt) -> PromptVersion | None:
    """Get the current (latest) version of a prompt."""
    return await get_version(db, prompt.id, prompt.current_version)


async def list_versions(
    db: AsyncSession, prompt_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[PromptVersion], int]:
    """List all versions of a prompt."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(PromptVersion.id)).where(PromptVersion.prompt_id == prompt_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version.desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def rollback_to_version(
    db: AsyncSession, prompt: Prompt, target_version: int
) -> PromptVersion:
    """Rollback a prompt to a previous version by creating a new version with old content."""
    target = await get_version(db, prompt.id, target_version)
    if target is None:
        raise VersionNotFoundError()

    return await _add_version(
        db, prompt,
        PromptVersionCreate(
            content=target.content,
            template_variables=target.template_variables,
            commit_message=f"Rollback to version {target_version}",
        ),
    )


# ─── Template Rendering ─────────────────────────────


def _extract_variables(template: str) -> list[str]:
    """Extract template variable names from a template string.
    
    Supports: {{variable_name}}, {{ variable_name }}, {variable_name}
    """
    variables = set()
    # Match {{ variable_name }} pattern
    for match in re.finditer(r"\{\{\s*(\w+)\s*\}\}", template):
        variables.add(match.group(1))
    # Match {variable_name} pattern (simple)
    for match in re.finditer(r"(?<!\{)\{(\w+)\}(?!\})", template):
        variables.add(match.group(1))
    return sorted(variables)


async def render_prompt(
    db: AsyncSession, prompt: Prompt, variables: dict[str, str] | None = None,
    version: int | None = None,
) -> str:
    """Render a prompt template with variables."""
    if version is not None:
        ver = await get_version(db, prompt.id, version)
    else:
        ver = await get_current_version(db, prompt)

    if ver is None:
        raise VersionNotFoundError()

    content = ver.content
    if variables:
        # Replace longest keys first to avoid partial replacements
        for key in sorted(variables.keys(), key=len, reverse=True):
            value = variables[key]
            content = content.replace("{{" + key + "}}", value)
            content = content.replace("{{ " + key + " }}", value)
            content = content.replace("{" + key + "}", value)

    return content

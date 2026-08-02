"""Prompt Registry API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404, require_workspace_role
from app.schemas.prompt import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptVersionCreate,
    PromptVersionResponse,
)
from app.models.user import User
from app.models.workspace import Workspace, MembershipRole
from app.models.prompt import Prompt
from app.services import prompt_service

router = APIRouter(tags=["Prompts"], redirect_slashes=False)


# ─── Dependency ─────────────────────────────────────


async def get_prompt_or_404(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Prompt:
    """Get a prompt and verify access."""
    prompt = await prompt_service.get_prompt_by_id(db, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    # Check access for workspace-scoped prompts
    if prompt.workspace_id and not current_user.is_superuser:
        from app.services import workspace_service
        membership = await workspace_service.get_workspace_membership(
            db, current_user.id, prompt.workspace_id
        )
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return prompt


# ─── Workspace-scoped Prompts ───────────────────────


@router.get(
    "/workspaces/{workspace_id}/prompts",
    response_model=list[PromptResponse],
)
@router.get(
    "/workspaces/{workspace_id}/prompts/",
    response_model=list[PromptResponse],
)
async def list_prompts(
    workspace: Workspace = Depends(get_workspace_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List prompts in a workspace."""
    prompts, total = await prompt_service.list_workspace_prompts(
        db, workspace.id, page=page, page_size=page_size
    )
    return [PromptResponse.model_validate(p) for p in prompts]


@router.post(
    "/workspaces/{workspace_id}/prompts",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/workspaces/{workspace_id}/prompts/",
    response_model=PromptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt(
    prompt_in: PromptCreate,
    workspace: Workspace = Depends(require_workspace_role(MembershipRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create a prompt in a workspace (Admin+)."""
    try:
        prompt = await prompt_service.create_prompt(db, prompt_in, workspace_id=workspace.id)
        return PromptResponse.model_validate(prompt)
    except prompt_service.PromptSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


# ─── Public Prompts ─────────────────────────────────


@router.post("/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_global_prompt(
    prompt_in: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a global prompt (no workspace context)."""
    try:
        prompt = await prompt_service.create_prompt(db, prompt_in, workspace_id=None)
        return PromptResponse.model_validate(prompt)
    except prompt_service.PromptSlugTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("/prompts/public", response_model=list[PromptResponse])
async def list_public_prompts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all public prompts."""
    prompts, total = await prompt_service.list_workspace_prompts(
        db, None, page=page, page_size=page_size
    )
    return [PromptResponse.model_validate(p) for p in prompts]


# ─── Single Prompt Operations ───────────────────────


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt: Prompt = Depends(get_prompt_or_404)):
    """Get a prompt by ID."""
    return PromptResponse.model_validate(prompt)


@router.patch("/prompts/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_in: PromptUpdate,
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Update prompt metadata."""
    prompt = await prompt_service.update_prompt(db, prompt, prompt_in)
    return PromptResponse.model_validate(prompt)


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt (soft-delete)."""
    await prompt_service.delete_prompt(db, prompt)
    return None


# ─── Version Management ─────────────────────────────


@router.get(
    "/prompts/{prompt_id}/versions",
    response_model=list[PromptVersionResponse],
)
async def list_versions(
    prompt: Prompt = Depends(get_prompt_or_404),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a prompt."""
    versions, total = await prompt_service.list_versions(
        db, prompt.id, page=page, page_size=page_size
    )
    return [PromptVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/prompts/{prompt_id}/versions",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    version_in: PromptVersionCreate,
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of a prompt."""
    version = await prompt_service.create_version(db, prompt, version_in)
    return PromptVersionResponse.model_validate(version)


@router.get(
    "/prompts/{prompt_id}/versions/{version}",
    response_model=PromptVersionResponse,
)
async def get_version(
    version: int,
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific version of a prompt."""
    ver = await prompt_service.get_version(db, prompt.id, version)
    if ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return PromptVersionResponse.model_validate(ver)


@router.post(
    "/prompts/{prompt_id}/rollback/{version}",
    response_model=PromptVersionResponse,
)
async def rollback_version(
    version: int,
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Rollback to a previous version (creates a new version with old content)."""
    try:
        ver = await prompt_service.rollback_to_version(db, prompt, version)
        return PromptVersionResponse.model_validate(ver)
    except prompt_service.VersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")


# ─── Template Rendering ─────────────────────────────


@router.post(
    "/prompts/{prompt_id}/render",
    response_model=dict,
)
async def render_prompt(
    variables: dict[str, str] | None = None,
    version: int | None = Query(None),
    prompt: Prompt = Depends(get_prompt_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Render a prompt template with variable substitution."""
    try:
        content = await prompt_service.render_prompt(db, prompt, variables, version=version)
        return {"content": content, "prompt_id": str(prompt.id), "version": version or prompt.current_version}
    except prompt_service.VersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

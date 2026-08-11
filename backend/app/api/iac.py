"""Infrastructure as Code API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
import yaml

from app.api.deps import get_current_active_user
from app.api.workspaces import get_workspace_or_404
from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import iac_service

router = APIRouter(prefix="/workspaces/{workspace_id}/iac", tags=["iac"])


class IaCImport(BaseModel):
    manifest: dict = Field(..., description="IaC manifest to import")
    dry_run: bool = Field(False, description="Preview without importing")


@router.get("/export")
async def export_iac(
    workspace_id: str,
    format: str = "yaml",
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Export workspace resources as IaC manifest."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    manifest = iac_service.export_workspace_as_iac(db, workspace["id"])
    
    if format == "json":
        return manifest
    
    # YAML format
    yaml_content = yaml.dump(manifest, default_flow_style=False, sort_keys=False)
    return Response(
        content=yaml_content,
        media_type="text/yaml",
        headers={"Content-Disposition": f"attachment; filename=agentos-{workspace['id'][:8]}.yaml"},
    )


@router.get("/export/json")
async def export_iac_json(
    workspace_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Export workspace resources as JSON IaC manifest."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return iac_service.export_workspace_as_iac(db, workspace["id"])


@router.post("/import")
async def import_iac(
    workspace_id: str,
    import_in: IaCImport,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Import an IaC manifest into a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    return iac_service.import_iac_to_workspace(
        db, workspace["id"],
        manifest=import_in.manifest,
        dry_run=import_in.dry_run,
    )


@router.post("/import/yaml")
async def import_iac_yaml(
    workspace_id: str,
    body: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Import a YAML IaC manifest into a workspace."""
    workspace = await get_workspace_or_404(workspace_id, db, current_user)
    try:
        manifest = yaml.safe_load(body)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    return iac_service.import_iac_to_workspace(db, workspace["id"], manifest=manifest)

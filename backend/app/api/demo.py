"""Demo workspace API — one-click first-run experience."""

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.services.demo_service import seed_demo_workspace

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed", status_code=201)
async def seed_demo(
    db=Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Create (or return) a populated demo workspace for the current user."""
    workspace = await seed_demo_workspace(db, current_user)
    return {
        "id": workspace["id"],
        "name": workspace.get("name"),
        "slug": workspace.get("slug"),
        "message": "Demo workspace loaded — explore the agents, workflow, prompts and tools.",
    }

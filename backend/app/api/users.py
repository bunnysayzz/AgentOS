"""User management API routes (Firestore-backed, Firebase auth)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.deps import get_current_user, get_current_active_user, require_superuser
from app.schemas.user import UserResponse, UserUpdate, UserListResponse, UserLookupResponse, PasswordChange
from app.services import auth_service, account_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Get the current user's profile."""
    return current_user


@router.get("/me/export")
async def export_my_data(
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """GDPR data-portability export: JSON snapshot of everything the user
    owns or participates in (workspaces, agents, workflows, secrets…)."""
    data = await account_service.export_user_data(db, current_user)
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": (
                f'attachment; filename="agentos-export-{current_user["id"]}.json"'
            )
        },
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """GDPR right-to-be-forgotten: permanently delete all of the current
    user's data (owned workspaces and their contents, memberships, API keys,
    profile). The Firebase Auth credential is handled client-side."""
    await account_service.delete_user_data(db, current_user)
    return None


@router.get("/lookup", response_model=UserLookupResponse)
async def lookup_user_by_email(
    email: str = Query(..., min_length=3),
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Look up a user by email (used by the Add Member flow).

    Registered BEFORE /{user_id} so "lookup" is never captured as an id.
    Returns only a slim public profile (never is_superuser/login metadata)
    so the caller can add the person without copy-pasting raw UUIDs.
    """
    user = auth_service.get_user_by_email(db, email.strip().lower())
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with that email")
    return UserLookupResponse(
        id=user["id"],
        email=user["email"],
        username=user.get("username") or "",
        full_name=user.get("full_name"),
        avatar_url=user.get("avatar_url"),
    )


@router.get("", response_model=UserListResponse)
@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(require_superuser),
):
    """List all users (superuser only)."""
    users, total = auth_service.list_users(db, page=page, page_size=page_size)
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a user by ID."""
    if current_user["id"] != str(user_id) and not current_user["is_superuser"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_in: UserUpdate,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a user profile."""
    if current_user["id"] != str(user_id) and not current_user["is_superuser"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = user_in.model_dump(exclude_unset=True)
    if updates.get("email"):
        existing = auth_service.get_user_by_email(db, updates["email"])
        if existing and existing["id"] != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )

    updated = auth_service.update_user(db, user_id, updates)
    return updated


@router.post("/password", status_code=status.HTTP_400_BAD_REQUEST)
async def change_password(
    body: PasswordChange,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(get_current_active_user),
):
    """Password changes go through Firebase Auth (client-side), not the backend."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Passwords are managed by Firebase Auth — change it from the app's security settings.",
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: FirestoreDB = Depends(get_db),
    current_user: dict = Depends(require_superuser),
):
    """Soft-delete a user (superuser only)."""
    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user["id"] == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    auth_service.soft_delete_user(db, user_id)
    return None

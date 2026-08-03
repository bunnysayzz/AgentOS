"""Auth API routes (Firebase-only).

Email/password signup and sign-in happen client-side via Firebase Auth.
This router exposes:

- ``POST /auth/firebase`` — exchange a Firebase ID token for the user profile
  (auto-creates the Firestore user on first sign-in).
- ``GET /auth/me`` — current user profile.
- ``POST /auth/logout`` — no-op (client clears its own session).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.api.deps import get_current_user
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


class FirebaseAuthRequest(BaseModel):
    id_token: str


@router.post("/firebase", response_model=UserResponse)
async def firebase_login(body: FirebaseAuthRequest, db: FirestoreDB = Depends(get_db)):
    """Exchange a Firebase ID token for the user profile (auto-register)."""
    try:
        claims = verify_firebase_token(body.id_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return auth_service.get_or_create_user_from_firebase(db, claims)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout (client-side token invalidation)."""
    return None

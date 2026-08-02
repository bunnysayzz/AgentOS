"""Auth API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserCreate, UserResponse
from app.models.user import User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    try:
        user = await auth_service.register_user(db, user_in)
        return user
    except auth_service.UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    try:
        return await auth_service.login_user(db, body.email, body.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    except auth_service.AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh an expired access token using a refresh token."""
    try:
        return await auth_service.refresh_user_tokens(db, body.refresh_token)
    except auth_service.TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


from pydantic import BaseModel, EmailStr

class GoogleAuthRequest(BaseModel):
    id_token: str | None = None
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate or auto-register a user using Google OAuth."""
    email = body.email
    full_name = body.full_name or email.split("@")[0]
    avatar_url = body.avatar_url

    if body.id_token:
        try:
            from firebase_admin import auth as fb_auth
            fb_decoded = fb_auth.verify_id_token(body.id_token)
            email = fb_decoded.get("email") or email
            full_name = fb_decoded.get("name") or full_name
            avatar_url = fb_decoded.get("picture") or avatar_url
        except Exception:
            pass

    user, token_resp = await auth_service.authenticate_or_create_google_user(
        db, email=email, full_name=full_name, avatar_url=avatar_url
    )
    return token_resp


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client-side token invalidation)."""
    return None

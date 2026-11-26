"""Authentication endpoints.

The access token is delivered only as an HTTP-only cookie, so page scripts (and
anything injected into them) cannot read it.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.rate_limit import limit_auth_attempt
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import UserLoginRequest, UserRead, UserRegisterRequest
from app.services import auth as auth_service
from app.services.exceptions import AuthenticationError, ConflictError

router = APIRouter()


def _set_access_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.access_cookie_name,
        value=create_access_token(user.id, user.role),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_access_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.access_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer account",
)
def register(
    payload: UserRegisterRequest, response: Response, db: Session = Depends(get_db),
    _: None = Depends(limit_auth_attempt),
) -> User:
    try:
        user = auth_service.register_user(db, payload)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # Registering signs the customer in immediately.
    _set_access_cookie(response, user)
    return user


@router.post("/login", response_model=UserRead, summary="Sign in and receive a session cookie")
def login(payload: UserLoginRequest, response: Response, db: Session = Depends(get_db),
          _: None = Depends(limit_auth_attempt)) -> User:
    try:
        user = auth_service.authenticate_user(db, payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_access_cookie(response, user)
    return user


@router.post("/logout", response_model=MessageResponse, summary="Clear the session cookie")
def logout(response: Response) -> MessageResponse:
    _clear_access_cookie(response)
    return MessageResponse(detail="Signed out")


@router.get("/me", response_model=UserRead, summary="Return the signed-in user")
def read_current_user(user: User = Depends(get_current_user)) -> User:
    return user

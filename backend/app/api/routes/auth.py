from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.admin_auth import require_admin_user
from app.config import get_settings
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_admin_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class SeedAdminRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


class AuthResponse(BaseModel):
    user: dict[str, Any]


def remove_password_hash(user: dict) -> dict:
    return {
        key: value
        for key, value in user.items()
        if key != "password_hash"
    }


def set_admin_auth_cookie(response: Response, access_token: str) -> None:
    settings = get_settings()

    response.set_cookie(
        key=settings.jwt_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
        path="/",
    )


def clear_admin_auth_cookie(response: Response) -> None:
    settings = get_settings()

    response.delete_cookie(
        key=settings.jwt_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response):
    user = authenticate_user(
        email=payload.email,
        password=payload.password,
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou senha invalidos.",
        )

    access_token = create_access_token({"sub": user["id"]})
    set_admin_auth_cookie(response, access_token)

    return {
        "user": remove_password_hash(user),
    }


@router.get("/me")
def get_current_admin_user(
    user: dict = Depends(require_admin_user),
):
    return remove_password_hash(user)


@router.post("/logout")
def logout(response: Response):
    clear_admin_auth_cookie(response)
    return {"message": "Sessao encerrada com sucesso."}


# Endpoint temporario para ambiente local/demo.
@router.post("/admin/seed")
def seed_admin_user(payload: SeedAdminRequest):
    try:
        return create_admin_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

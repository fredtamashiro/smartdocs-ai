from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.services.auth_service import get_user_by_id

security = HTTPBearer(auto_error=False)


def require_admin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    settings = get_settings()
    token = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        token = request.cookies.get(settings.jwt_cookie_name)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Nao autenticado.",
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Token de autenticacao invalido.",
            )
    except JWTError as error:
        raise HTTPException(
            status_code=401,
            detail="Token de autenticacao invalido.",
        ) from error

    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=403,
            detail="Usuario sem permissao de administrador.",
        )

    if not user["is_active"] or user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Usuario sem permissao de administrador.",
        )

    return user

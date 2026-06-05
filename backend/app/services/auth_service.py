from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import text

from app.config import get_settings
from app.database.database import SessionLocal

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def serialize_user(row, include_password_hash: bool = True) -> dict | None:
    if row is None:
        return None

    mapping = row._mapping
    user = {
        "id": str(mapping["id"]),
        "email": mapping["email"],
        "name": mapping["name"],
        "role": mapping["role"],
        "is_active": mapping["is_active"],
    }

    if include_password_hash:
        user["password_hash"] = mapping["password_hash"]

    return user


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return password_context.verify(plain_password, password_hash)


def create_access_token(data: dict) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes,
    )

    payload = data.copy()
    payload.update({"exp": expires_at})

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def get_user_by_email(email: str) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active
                FROM auth.users
                WHERE email = :email
                """
            ),
            {"email": email},
        ).fetchone()

    return serialize_user(row)


def get_user_by_id(user_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    id,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active
                FROM auth.users
                WHERE id = CAST(:user_id AS UUID)
                """
            ),
            {"user_id": user_id},
        ).fetchone()

    return serialize_user(row)


def authenticate_user(email: str, password: str) -> dict | None:
    user = get_user_by_email(email)

    if not user:
        return None

    if not user["is_active"]:
        return None

    if not user["password_hash"]:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return user


def create_admin_user(
    email: str,
    password: str,
    name: str | None = None,
) -> dict:
    existing_user = get_user_by_email(email)

    if existing_user:
        raise ValueError("Ja existe um usuario com esse email.")

    user_id = str(uuid4())
    password_hash = hash_password(password)

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                INSERT INTO auth.users (
                    id,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active
                )
                VALUES (
                    CAST(:id AS UUID),
                    :email,
                    :name,
                    :password_hash,
                    'admin',
                    TRUE
                )
                RETURNING
                    id,
                    email,
                    name,
                    password_hash,
                    role,
                    is_active
                """
            ),
            {
                "id": user_id,
                "email": email,
                "name": name,
                "password_hash": password_hash,
            },
        ).fetchone()
        db.commit()

    return serialize_user(row, include_password_hash=False)

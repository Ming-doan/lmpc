from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db
from src.models.admin import Admin, Session as AdminSession
from src.auth.utils import verify_password, generate_token, hash_token
from src.schemas.auth import LoginRequest
from src.config import settings

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.email == body.email))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = generate_token()
    session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    await db.commit()
    response.set_cookie(settings.session_cookie_name, token, httponly=True, samesite="lax")
    return {"ok": True}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}

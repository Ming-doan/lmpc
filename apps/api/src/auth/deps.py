from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from src.db import get_db
from src.models.admin import Admin, Session as AdminSession
from src.auth.utils import hash_token
from src.config import settings


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """Get the currently authenticated admin user via session cookie"""
    # Get session token from cookies
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Hash the token and look up session in DB
    token_hash = hash_token(token)
    result = await db.execute(
        select(AdminSession).where(
            AdminSession.token_hash == token_hash,
            AdminSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Look up admin user in DB
    result = await db.execute(select(Admin).where(Admin.id == session.admin_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return admin

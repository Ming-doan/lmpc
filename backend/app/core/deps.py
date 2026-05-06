import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import hash_token, _bearer, _token_from
from app.models.worker import Worker

_worker_bearer = HTTPBearer(auto_error=False)


async def get_current_worker(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Worker:
    token = _token_from(credentials)
    token_hash = hash_token(token)
    result = await db.execute(
        select(Worker).where(Worker.api_token_hash == token_hash)
    )
    worker = result.scalar_one_or_none()
    if worker is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker token")
    if not worker.approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker not approved")
    return worker

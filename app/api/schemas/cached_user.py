from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CachedUser(BaseModel):
    """
    A Pydantic model representing the data of a User object to be stored in the cache.
    This avoids caching the full SQLAlchemy ORM object, which prevents DetachedInstanceError
    and improves performance by removing the need for `db.merge()`.
    """

    id: int
    email: EmailStr
    username: str
    is_active: bool
    clerk_user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

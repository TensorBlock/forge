import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base

# UsageStats model is removed, so no related imports needed


class User(Base):
    """User model for storing user information"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # is_admin = Column(Boolean, default=False) # Add if implementing admin role
    clerk_user_id = Column(String, unique=True, nullable=True)  # Add Clerk user ID
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    api_keys = relationship(
        "ForgeApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    provider_keys = relationship(
        "ProviderKey", back_populates="user", cascade="all, delete-orphan"
    )
    # Optional: Add relationship to ApiRequestLog if needed
    # api_logs = relationship("ApiRequestLog")

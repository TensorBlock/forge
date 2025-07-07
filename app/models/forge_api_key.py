import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from app.models.base import Base

# Association Table for ForgeApiKey and ProviderKey
forge_api_key_provider_scope_association = Table(
    "forge_api_key_provider_scope_association",
    Base.metadata,
    Column(
        "forge_api_key_id",
        Integer,
        ForeignKey("forge_api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "provider_key_id",
        Integer,
        ForeignKey("provider_keys.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ForgeApiKey(Base):
    """Model for storing multiple Forge API keys per user"""

    __tablename__ = "forge_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)  # Optional name/description for the key
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    # Relationship to user
    user = relationship("User", back_populates="api_keys")

    # Relationship to allowed ProviderKeys (scope)
    allowed_provider_keys = relationship(
        "ProviderKey",
        secondary=forge_api_key_provider_scope_association,
        back_populates="scoped_forge_api_keys",
        lazy="selectin",  # Use selectin loading for efficiency when accessing this relationship
    )

    # Optionally, we could have a relationship to enabled provider keys
    # enabled_provider_keys = relationship("EnabledProviderKey", back_populates="api_key")

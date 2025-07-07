from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.forge_api_key import forge_api_key_provider_scope_association

from .base import BaseModel


class ProviderKey(BaseModel):
    __tablename__ = "provider_keys"

    provider_name = Column(String, index=True)  # e.g., "openai", "anthropic", etc.
    encrypted_api_key = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="provider_keys")

    # Additional metadata specific to the provider
    base_url = Column(
        String, nullable=True
    )  # Allow custom base URLs for some providers
    model_mapping = Column(String, nullable=True)  # JSON string for model name mappings

    # Relationship to ForgeApiKeys that have this provider key in their scope
    scoped_forge_api_keys = relationship(
        "ForgeApiKey",
        secondary=forge_api_key_provider_scope_association,
        back_populates="allowed_provider_keys",
        lazy="selectin",
    )

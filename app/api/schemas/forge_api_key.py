from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ForgeApiKeyBase(BaseModel):
    """Base schema for ForgeApiKey"""

    name: str | None = None


class ForgeApiKeyCreate(ForgeApiKeyBase):
    """Schema for creating a ForgeApiKey"""

    allowed_provider_key_ids: list[int] | None = Field(default=None)


class ForgeApiKeyResponse(ForgeApiKeyBase):
    """Schema for ForgeApiKey response"""

    id: int
    key: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    allowed_provider_key_ids: list[int] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ForgeApiKeyMasked(ForgeApiKeyBase):
    """Schema for ForgeApiKey with masked key for display"""

    id: int
    key: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    allowed_provider_key_ids: list[int] = Field(default_factory=list)

    @staticmethod
    def mask_api_key(key: str) -> str:
        """Mask the API key for display"""
        if not key:
            return ""
        if key.startswith("forge-"):
            prefix = "forge-"
            key_part = key[len(prefix) :]
            return f"{prefix}{'*' * (len(key_part) - 4)}{key_part[-4:]}"
        return f"{'*' * (len(key) - 4)}{key[-4:]}"

    model_config = ConfigDict(from_attributes=True)


class ForgeApiKeyUpdate(BaseModel):
    """Schema for updating a ForgeApiKey"""

    name: str | None = None
    is_active: bool | None = None
    allowed_provider_key_ids: list[int] | None = None

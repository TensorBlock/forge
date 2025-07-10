import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field, Field, field_validator

from app.core.logger import get_logger
from app.core.security import decrypt_api_key
from app.services.providers.adapter_factory import ProviderAdapterFactory

logger = get_logger(name="provider_key")


class ProviderKeyBase(BaseModel):
    provider_name: str = Field(..., min_length=1)
    api_key: str
    base_url: str | None = None
    model_mapping: dict[str, str] | None = None
    config: dict[str, str] | None = None


class ProviderKeyCreate(ProviderKeyBase):
    pass


class ProviderKeyUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model_mapping: dict[str, str] | None = None


class ProviderKeyInDBBase(BaseModel):
    id: int
    provider_name: str
    user_id: int
    base_url: str | None = None
    model_mapping: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime
    encrypted_api_key: str
    model_config = ConfigDict(from_attributes=True)

    @field_validator("model_mapping", mode="before")
    @classmethod
    def parse_model_mapping(cls, v):
        """Parse JSON string to dictionary for model_mapping field."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse model_mapping JSON: {v}")
                return {}
        return v


class ProviderKey(ProviderKeyInDBBase):
    @computed_field
    @property
    def api_key(self) -> str | None:
        """Masked API key for responses."""
        if self.encrypted_api_key:
            decrypted_value = decrypt_api_key(self.encrypted_api_key)
            provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(
                self.provider_name
            )
            try:
                api_key, _ = provider_adapter_cls.deserialize_api_key_config(
                    decrypted_value
                )
                return provider_adapter_cls.mask_api_key(api_key)
            except Exception as e:
                logger.error(
                    f"Error deserializing API key for provider {self.provider_name}: {e}"
                )
                return None
        return None

    @computed_field
    @property
    def config(self) -> dict[str, str] | None:
        """Masked config for responses."""
        if self.encrypted_api_key:
            decrypted_value = decrypt_api_key(self.encrypted_api_key)
            provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(
                self.provider_name
            )
            try:
                _, config = provider_adapter_cls.deserialize_api_key_config(
                    decrypted_value
                )
                return provider_adapter_cls.mask_config(config)
            except Exception as e:
                logger.error(
                    f"Error deserializing config for provider {self.provider_name}: {e}"
                )
                return None
        return None


class ProviderKeyUpsertItem(BaseModel):
    provider_name: str = Field(..., min_length=1)
    api_key: str | None = None
    base_url: str | None = None
    model_mapping: dict[str, str] | None = None
    config: dict[str, str] | None = None

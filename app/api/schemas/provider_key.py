from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field, Field

from app.core.logger import get_logger
from app.core.security import decrypt_api_key
from app.services.providers.adapter_factory import ProviderAdapterFactory

logger = get_logger(name="provider_key")

# Constants for API key masking
API_KEY_MASK_PREFIX_LENGTH = 2
API_KEY_MASK_SUFFIX_LENGTH = 4
# Minimum length to apply the full prefix + suffix mask (e.g., pr******fix)
# This means if length is > (PREFIX + SUFFIX), we can apply the full rule.
MIN_KEY_LENGTH_FOR_FULL_MASK_LOGIC = (
    API_KEY_MASK_PREFIX_LENGTH + API_KEY_MASK_SUFFIX_LENGTH
)


# Helper function for masking API keys
def _mask_api_key_value(value: str | None) -> str | None:
    if not value:
        return None

    length = len(value)

    if length == 0:
        return ""

    # If key is too short for any meaningful prefix/suffix masking
    if length <= API_KEY_MASK_PREFIX_LENGTH:
        return "*" * length

    # If key is long enough for prefix, but not for prefix + suffix
    # e.g., length is 3, 4, 5, 6. For these, show prefix and mask the rest.
    if length <= MIN_KEY_LENGTH_FOR_FULL_MASK_LOGIC:
        return value[:API_KEY_MASK_PREFIX_LENGTH] + "*" * (
            length - API_KEY_MASK_PREFIX_LENGTH
        )

    # If key is long enough for the full prefix + ... + suffix mask
    # number of asterisks = length - prefix_length - suffix_length
    num_asterisks = length - API_KEY_MASK_PREFIX_LENGTH - API_KEY_MASK_SUFFIX_LENGTH
    return (
        value[:API_KEY_MASK_PREFIX_LENGTH]
        + "*" * num_asterisks
        + value[-API_KEY_MASK_SUFFIX_LENGTH:]
    )


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
                return _mask_api_key_value(api_key)
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

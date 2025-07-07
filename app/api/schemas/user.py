from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.schemas.forge_api_key import ForgeApiKeyMasked

# Constants
VISIBLE_API_KEY_CHARS = 4


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str | None = None


class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class User(UserInDB):
    forge_api_keys: list[str] | None = None


class MaskedUser(UserInDB):
    forge_api_keys: list[str] | None = Field(
        description="List of all API keys with all but last 4 digits masked",
        default=None,
    )

    @classmethod
    def mask_api_key(cls, api_key: str | None) -> str | None:
        if not api_key:
            return None
        return ForgeApiKeyMasked.mask_api_key(api_key)

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None

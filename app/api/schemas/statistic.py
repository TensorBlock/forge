from pydantic import BaseModel, field_validator
from datetime import datetime
import re
import decimal

from app.api.schemas.forge_api_key import ForgeApiKeyMasked

def mask_forge_name_or_key(v: str) -> str:
    # If the forge key is a valid forge key, mask it
    if re.match(r"forge-\w{18}", v):
        return ForgeApiKeyMasked.mask_api_key(v)
    # Otherwise, return the original value (user customized name)
    return v

class UsageRealtimeResponse(BaseModel):
    timestamp: datetime
    forge_key: str
    provider_name: str
    model_name: str
    tokens: int
    duration: float
    cost: decimal.Decimal
    
    @field_validator('forge_key')
    @classmethod
    def mask_forge_key(cls, v: str) -> str:
        return mask_forge_name_or_key(v)

    @field_validator('timestamp')
    @classmethod
    def convert_timestamp_to_iso(cls, v: datetime) -> str:
        return v.isoformat()


class UsageSummaryBreakdown(BaseModel):
    forge_key: str
    tokens: int
    cost: decimal.Decimal

    @field_validator('forge_key')
    @classmethod
    def mask_forge_key(cls, v: str) -> str:
        return mask_forge_name_or_key(v)


class UsageSummaryResponse(BaseModel):
    time_point: datetime
    breakdown: list[UsageSummaryBreakdown]
    total_tokens: int
    total_cost: decimal.Decimal

    @field_validator('time_point')
    @classmethod
    def convert_timestamp_to_iso(cls, v: datetime) -> str:
        return v.isoformat()


class ForgeKeysUsageSummaryResponse(BaseModel):
    forge_key: str
    tokens: int
    cost: decimal.Decimal

    @field_validator('forge_key')
    @classmethod
    def mask_forge_key(cls, v: str) -> str:
        return mask_forge_name_or_key(v)
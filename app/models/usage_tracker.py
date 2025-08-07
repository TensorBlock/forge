import datetime
from datetime import UTC
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class UsageTracker(Base):
    __tablename__ = "usage_tracker"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider_key_id = Column(Integer, ForeignKey("provider_keys.id", ondelete="CASCADE"), nullable=False)
    forge_key_id = Column(Integer, ForeignKey("forge_api_keys.id", ondelete="CASCADE"), nullable=False)
    model = Column(String, nullable=True)
    endpoint = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cached_tokens = Column(Integer, nullable=True)
    reasoning_tokens = Column(Integer, nullable=True)

import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String

from .base import Base


class ApiRequestLog(Base):
    __tablename__ = "api_request_log"

    id = Column(Integer, primary_key=True)
    # Link to user, allow null if user deleted or request is unauthenticated? Let's make it nullable.
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_name = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False, index=True)  # e.g., 'chat/completions'
    request_timestamp = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )  # Time of the request
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)  # Calculated: input + output
    cost = Column(Float, default=0.0)  # Estimated cost if available
    # Optional: Add status_code and duration_ms later if needed

    # Relationship (optional, useful if querying logs through User object)
    # user = relationship("User")

    # Define indices for common query patterns
    __table_args__ = (
        Index("ix_api_request_log_user_time", "user_id", "request_timestamp"),
        # Add other indices as needed, e.g., Index('ix_api_request_log_provider_model', 'provider_name', 'model')
    )

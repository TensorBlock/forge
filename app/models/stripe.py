from app.models.base import Base
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime
from datetime import datetime, UTC

class StripePayment(Base):
    __tablename__ = "stripe_payment"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String, nullable=False)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=datetime.now(UTC), onupdate=datetime.now(UTC))
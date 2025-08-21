from datetime import datetime, UTC
from sqlalchemy import Column, BigInteger, CHAR, DECIMAL, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Wallet(Base):
    __tablename__ = "wallets"

    account_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    currency = Column(CHAR(3), nullable=False, default='USD')
    balance = Column(DECIMAL(20, 6), nullable=False, default=0)
    blocked = Column(Boolean, nullable=False, default=False)
    version = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(UTC))

    user = relationship("User", back_populates="wallet")
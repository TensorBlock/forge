# app/models/pricing.py
import datetime
from datetime import UTC
from sqlalchemy import Column, DateTime, String, DECIMAL, Index

from .base import BaseModel


class ModelPricing(BaseModel):
    """
    Store pricing information for specific models with temporal support
    """
    __tablename__ = "model_pricing"

    provider_name = Column(String, nullable=False, index=True)
    model_name = Column(String, nullable=False, index=True)
    
    # Temporal fields for price changes over time
    effective_date = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now(UTC))
    end_date = Column(DateTime(timezone=True), nullable=True)  # NULL means currently active
    
    # Pricing per 1K tokens (using DECIMAL for precision)
    input_token_price = Column(DECIMAL(12, 8), nullable=False)  # Price per 1K input tokens
    output_token_price = Column(DECIMAL(12, 8), nullable=False)  # Price per 1K output tokens
    cached_token_price = Column(DECIMAL(12, 8), nullable=False, default=0)  # Price per 1K cached tokens
    
    # Metadata
    currency = Column(String(3), nullable=False, default='USD')
    
    # Indexes for efficient querying
    __table_args__ = (
        # Index for finding active pricing for a model
        Index('ix_model_pricing_active', 'provider_name', 'model_name', 'effective_date', 'end_date'),
        # Index for temporal queries
        Index('ix_model_pricing_temporal', 'effective_date', 'end_date'),
        # Unique constraint for overlapping periods (business rule enforcement)
        Index('ix_model_pricing_unique_period', 'provider_name', 'model_name', 'effective_date', unique=True),
    )


class FallbackPricing(BaseModel):
    """
    Store fallback pricing for providers and global defaults
    """
    __tablename__ = "fallback_pricing"

    provider_name = Column(String, nullable=True, index=True)  # NULL for global fallback
    fallback_type = Column(String(20), nullable=False, index=True)  # 'provider_default', 'global_default'
    
    # Temporal fields
    effective_date = Column(DateTime(timezone=True), nullable=False, default=datetime.datetime.now(UTC))
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Pricing per 1K tokens
    input_token_price = Column(DECIMAL(12, 8), nullable=False)
    output_token_price = Column(DECIMAL(12, 8), nullable=False)
    cached_token_price = Column(DECIMAL(12, 8), nullable=False, default=0)
    
    # Metadata
    currency = Column(String(3), nullable=False, default='USD')
    description = Column(String(255), nullable=True)  # Optional description
    
    # Indexes
    __table_args__ = (
        Index('ix_fallback_pricing_active', 'provider_name', 'fallback_type', 'effective_date', 'end_date'),
        Index('ix_fallback_pricing_type', 'fallback_type', 'effective_date'),
    )

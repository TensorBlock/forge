import hashlib
from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, Optional, Any
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.async_cache import async_provider_service_cache
from app.models.pricing import ModelPricing, FallbackPricing

logger = get_logger(name="pricing_service")

class PricingService:
    """
    Cache-optimized pricing service that minimizes database hits
    
    Cache Strategy:
    1. Exact match cache: Active model pricing (TTL: 1 day)
    2. Fallback cache: Provider fallback pricing (TTL: 12 hours) 
    3. Emergency fallback: Hard-coded prices (TTL: 6 hours)
    """
    
    # Cache TTL constants
    EXACT_CACHE_TTL = 86400   # 1 day - active model pricing
    FALLBACK_CACHE_TTL = 43200  # 12 hours - provider fallbacks
    EMERGENCY_CACHE_TTL = 21600  # 6 hours - emergency fallback
    
    # Emergency fallback prices (per 1K tokens)
    EMERGENCY_PRICING = {
        'input_price': Decimal('0.01'),
        'output_price': Decimal('0.03'), 
        'cached_price': Decimal('0.001'),
        'currency': 'USD'
    }
    
    @staticmethod
    async def calculate_usage_cost(
        db: AsyncSession,
        provider_name: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        calculation_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate token costs with aggressive caching to minimize DB hits
        """
        if calculation_date is None:
            calculation_date = datetime.now(UTC)
        
        # Generate cache key for this exact pricing lookup
        cache_key = PricingService._generate_pricing_cache_key(
            provider_name, model_name, calculation_date
        )
        
        # Try to get complete pricing info from cache
        pricing_info = await async_provider_service_cache.get(cache_key)
        
        if pricing_info is None:
            # Cache miss - fetch pricing with smart fallback logic
            pricing_info = await PricingService._fetch_pricing_with_smart_caching(
                db, provider_name, model_name, calculation_date
            )
            
            # Cache the result with appropriate TTL based on data source
            ttl = PricingService._get_cache_ttl(pricing_info['source'])
            await async_provider_service_cache.set(cache_key, pricing_info, ttl=ttl)
            
            logger.debug(f"Cached pricing for {provider_name}/{model_name} with TTL {ttl}s")
        
        # Calculate costs using cached pricing
        input_tokens = prompt_tokens - cached_tokens
        output_tokens = completion_tokens
        return PricingService._calculate_costs_from_pricing(
            pricing_info, input_tokens, output_tokens, cached_tokens
        )
    
    @staticmethod
    async def _fetch_pricing_with_smart_caching(
        db: AsyncSession,
        provider_name: str,
        model_name: str,
        calculation_date: datetime
    ) -> Dict[str, Any]:
        """
        Fetch pricing with smart caching at multiple levels
        """
        
        # Level 1: Try exact model cache (hot cache)
        exact_cache_key = f"pricing:exact:{provider_name}:{model_name}"
        exact_pricing = await async_provider_service_cache.get(exact_cache_key)
        
        if exact_pricing and PricingService._is_pricing_valid_for_date(exact_pricing, calculation_date):
            logger.debug(f"Hot cache hit for {provider_name}/{model_name}")
            return {**exact_pricing, 'source': 'exact_match'}
        
        # Level 2: Try provider fallback cache (warm cache)
        provider_cache_key = f"pricing:provider_fallback:{provider_name}"
        provider_fallback = await async_provider_service_cache.get(provider_cache_key)
        
        if provider_fallback and PricingService._is_pricing_valid_for_date(provider_fallback, calculation_date):
            logger.debug(f"Warm cache hit for provider {provider_name}")
            return {**provider_fallback, 'source': 'fallback_provider'}
        
        # Level 3: Try global fallback cache (warm cache)
        global_cache_key = f"pricing:global_fallback"
        global_fallback = await async_provider_service_cache.get(global_cache_key)
        
        if global_fallback and PricingService._is_pricing_valid_for_date(global_fallback, calculation_date):
            logger.debug("Warm cache hit for global fallback")
            return {**global_fallback, 'source': 'fallback_global'}
        
        # Cache miss - hit database (this should be rare)
        logger.info(f"Cache miss - fetching from DB for {provider_name}/{model_name}")
        return await PricingService._fetch_from_database_with_caching(
            db, provider_name, model_name, calculation_date
        )
    
    @staticmethod
    async def _fetch_from_database_with_caching(
        db: AsyncSession,
        provider_name: str,
        model_name: str,
        calculation_date: datetime
    ) -> Dict[str, Any]:
        """
        Fetch from database and populate multiple cache levels
        """
        
        # Try exact model match
        exact_pricing = await PricingService._get_exact_model_pricing_db(
            db, provider_name, model_name, calculation_date
        )
        
        if exact_pricing:
            # Cache exact model pricing (hot cache)
            cache_key = f"pricing:exact:{provider_name}:{model_name}"
            await async_provider_service_cache.set(
                cache_key, exact_pricing, ttl=PricingService.EXACT_CACHE_TTL
            )
            return {**exact_pricing, 'source': 'exact_match'}
        
        # Try provider fallback
        provider_fallback = await PricingService._get_provider_fallback_pricing_db(
            db, provider_name, calculation_date
        )
        
        if provider_fallback:
            # Cache provider fallback (warm cache)
            cache_key = f"pricing:provider_fallback:{provider_name}"
            await async_provider_service_cache.set(
                cache_key, provider_fallback, ttl=PricingService.FALLBACK_CACHE_TTL
            )
            logger.warning(f"Using provider fallback pricing for {provider_name}/{model_name}")
            return {**provider_fallback, 'source': 'fallback_provider'}
        
        # Try global fallback
        global_fallback = await PricingService._get_global_fallback_pricing_db(
            db, calculation_date
        )
        
        if global_fallback:
            # Cache global fallback (warm cache)
            cache_key = f"pricing:global_fallback"
            await async_provider_service_cache.set(
                cache_key, global_fallback, ttl=PricingService.FALLBACK_CACHE_TTL
            )
            logger.warning(f"Using global fallback pricing for {provider_name}/{model_name}")
            return {**global_fallback, 'source': 'fallback_global'}
        
        # Emergency fallback (never cache this - it's always available)
        logger.error(f"No pricing found for {provider_name}/{model_name}, using emergency fallback")
        return {**PricingService.EMERGENCY_PRICING, 'source': 'emergency_fallback'}
    
    @staticmethod
    async def warm_pricing_cache(db: AsyncSession, provider_names: Optional[list[str]] = None) -> Dict[str, int]:
        """
        Pre-warm the pricing cache with frequently accessed models and fallbacks
        This should be called periodically (e.g., via cron job)
        """
        stats = {'exact_models': 0, 'provider_fallbacks': 0, 'global_fallback': 0}
        current_time = datetime.now(UTC)
        
        # Get active pricing for all providers or specific ones
        query = select(ModelPricing).where(
            and_(
                ModelPricing.effective_date <= current_time,
                or_(ModelPricing.end_date.is_(None), ModelPricing.end_date > current_time)
            )
        )
        
        if provider_names:
            query = query.where(ModelPricing.provider_name.in_(provider_names))
        
        result = await db.execute(query)
        active_pricing = result.scalars().all()
        
        # Cache exact model pricing
        for pricing in active_pricing:
            cache_key = f"pricing:exact:{pricing.provider_name}:{pricing.model_name}"
            pricing_data = {
                'input_price': pricing.input_token_price,
                'output_price': pricing.output_token_price,
                'cached_price': pricing.cached_token_price,
                'currency': pricing.currency,
                'effective_date': pricing.effective_date.isoformat(),
                'end_date': pricing.end_date.isoformat() if pricing.end_date else None,
            }
            await async_provider_service_cache.set(
                cache_key, pricing_data, ttl=PricingService.EXACT_CACHE_TTL
            )
            stats['exact_models'] += 1
        
        # Cache provider fallbacks
        fallback_query = select(FallbackPricing).where(
            and_(
                FallbackPricing.effective_date <= current_time,
                or_(FallbackPricing.end_date.is_(None), FallbackPricing.end_date > current_time),
                FallbackPricing.fallback_type == 'provider_default'
            )
        )
        
        if provider_names:
            fallback_query = fallback_query.where(FallbackPricing.provider_name.in_(provider_names))
        
        result = await db.execute(fallback_query)
        provider_fallbacks = result.scalars().all()
        
        for fallback in provider_fallbacks:
            cache_key = f"pricing:provider_fallback:{fallback.provider_name}"
            fallback_data = {
                'input_price': fallback.input_token_price,
                'output_price': fallback.output_token_price,
                'cached_price': fallback.cached_token_price,
                'currency': 'USD',  # Assuming USD for fallbacks
                'effective_date': fallback.effective_date.isoformat(),
                'end_date': fallback.end_date.isoformat() if fallback.end_date else None,
            }
            await async_provider_service_cache.set(
                cache_key, fallback_data, ttl=PricingService.FALLBACK_CACHE_TTL
            )
            stats['provider_fallbacks'] += 1
        
        # Cache global fallback
        global_fallback_query = select(FallbackPricing).where(
            and_(
                FallbackPricing.effective_date <= current_time,
                or_(FallbackPricing.end_date.is_(None), FallbackPricing.end_date > current_time),
                FallbackPricing.fallback_type == 'global_default'
            )
        ).order_by(FallbackPricing.effective_date.desc()).limit(1)
        
        result = await db.execute(global_fallback_query)
        global_fallback = result.scalar_one_or_none()
        
        if global_fallback:
            cache_key = f"pricing:global_fallback"
            global_data = {
                'input_price': global_fallback.input_token_price,
                'output_price': global_fallback.output_token_price,
                'cached_price': global_fallback.cached_token_price,
                'currency': 'USD',
                'effective_date': global_fallback.effective_date.isoformat(),
                'end_date': global_fallback.end_date.isoformat() if global_fallback.end_date else None,
            }
            await async_provider_service_cache.set(
                cache_key, global_data, ttl=PricingService.FALLBACK_CACHE_TTL
            )
            stats['global_fallback'] = 1
        
        logger.info(f"Pricing cache warmed: {stats}")
        return stats
    
    @staticmethod
    async def invalidate_pricing_cache(
        provider_name: Optional[str] = None, 
        model_name: Optional[str] = None
    ) -> None:
        """
        Invalidate pricing cache entries
        """
        if provider_name and model_name:
            # Invalidate specific model
            cache_key = f"pricing:exact:{provider_name}:{model_name}"
            await async_provider_service_cache.delete(cache_key)
            logger.info(f"Invalidated pricing cache for {provider_name}/{model_name}")
            
        elif provider_name:
            # Invalidate entire provider
            await PricingService._invalidate_provider_pricing_cache(provider_name)
            logger.info(f"Invalidated pricing cache for provider {provider_name}")
            
        else:
            # Invalidate all pricing cache
            await PricingService._invalidate_all_pricing_cache()
            logger.info("Invalidated all pricing cache")
    
    @staticmethod
    async def _invalidate_provider_pricing_cache(provider_name: str) -> None:
        """Invalidate all cache entries for a specific provider"""
        prefixes = [
            f"pricing:exact:{provider_name}:",
            f"pricing:provider_fallback:{provider_name}",
            f"pricing:lookup:{provider_name}:"
        ]
        
        # Handle in-memory cache
        if hasattr(async_provider_service_cache, "cache"):
            async with async_provider_service_cache.lock:
                keys_to_delete = []
                for key in async_provider_service_cache.cache.keys():
                    if any(key.startswith(prefix) for prefix in prefixes):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    await async_provider_service_cache.delete(key)
        
        # Handle Redis cache
        if hasattr(async_provider_service_cache, "client"):
            try:
                for prefix in prefixes:
                    redis_pattern = f"{os.getenv('REDIS_PREFIX', 'forge')}:{prefix}*"
                    async for redis_key in async_provider_service_cache.client.scan_iter(match=redis_pattern):
                        key_str = redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                        internal_key = key_str.split(":", 1)[-1]
                        await async_provider_service_cache.delete(internal_key)
            except Exception as exc:
                logger.warning(f"Failed to invalidate Redis pricing cache: {exc}")
    
    @staticmethod
    async def _invalidate_all_pricing_cache() -> None:
        """Invalidate all pricing-related cache entries"""
        # Handle in-memory cache
        if hasattr(async_provider_service_cache, "cache"):
            async with async_provider_service_cache.lock:
                keys_to_delete = []
                for key in async_provider_service_cache.cache.keys():
                    if key.startswith("pricing:"):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    await async_provider_service_cache.delete(key)
        
        # Handle Redis cache
        if hasattr(async_provider_service_cache, "client"):
            try:
                redis_pattern = f"{os.getenv('REDIS_PREFIX', 'forge')}:pricing:*"
                async for redis_key in async_provider_service_cache.client.scan_iter(match=redis_pattern):
                    key_str = redis_key.decode() if isinstance(redis_key, bytes) else redis_key
                    internal_key = key_str.split(":", 1)[-1]
                    await async_provider_service_cache.delete(internal_key)
            except Exception as exc:
                logger.warning(f"Failed to invalidate all Redis pricing cache: {exc}")
    
    # Helper methods
    @staticmethod
    def _generate_pricing_cache_key(provider_name: str, model_name: str, calculation_date: datetime) -> str:
        """Generate a cache key for pricing lookups"""
        date_str = calculation_date.strftime("%Y-%m-%d")
        key_data = f"{provider_name}:{model_name}:{date_str}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"pricing:lookup:{provider_name}:{key_hash}"
    
    @staticmethod
    def _get_cache_ttl(source: str) -> int:
        """Get appropriate TTL based on pricing data source"""
        ttl_map = {
            'exact_match': PricingService.EXACT_CACHE_TTL,
            'fallback_provider': PricingService.FALLBACK_CACHE_TTL,
            'fallback_global': PricingService.FALLBACK_CACHE_TTL,
            'emergency_fallback': PricingService.EMERGENCY_CACHE_TTL,
        }
        return ttl_map.get(source, PricingService.EMERGENCY_CACHE_TTL)
    
    @staticmethod
    def _is_pricing_valid_for_date(pricing_info: Dict[str, Any], calculation_date: datetime) -> bool:
        """Check if cached pricing is valid for the given date"""
        if 'effective_date' not in pricing_info:
            return True  # Emergency fallback is always valid
        
        effective_date = datetime.fromisoformat(pricing_info['effective_date'])
        end_date = None
        if pricing_info.get('end_date'):
            end_date = datetime.fromisoformat(pricing_info['end_date'])
        
        return (calculation_date >= effective_date and 
                (end_date is None or calculation_date < end_date))
    
    @staticmethod
    def _calculate_costs_from_pricing(
        pricing_info: Dict[str, Any],
        input_tokens: int,
        output_tokens: int, 
        cached_tokens: int,
    ) -> Dict[str, Any]:
        """Calculate costs using pricing information"""
        input_cost = Decimal(str(input_tokens)) * pricing_info['input_price'] / 1000
        output_cost = Decimal(str(output_tokens)) * pricing_info['output_price'] / 1000
        cached_cost = Decimal(str(cached_tokens)) * pricing_info['cached_price'] / 1000
        
        total_cost = input_cost + output_cost + cached_cost
        
        return {
            'total_cost': total_cost,
            'breakdown': {
                'input_cost': input_cost,
                'output_cost': output_cost,
                'cached_cost': cached_cost,
            },
            'pricing_source': pricing_info['source'],
            'currency': pricing_info['currency']
        }

    # Database query methods (only called on cache misses)
    @staticmethod
    async def _get_exact_model_pricing_db(db: AsyncSession, provider_name: str, model_name: str, calculation_date: datetime) -> Optional[Dict[str, Any]]:
        """Get model pricing from database using longest prefix matching with pure SQL"""
        
        query = select(ModelPricing).where(
            ModelPricing.provider_name == provider_name,
            ModelPricing.effective_date <= calculation_date,
            or_(ModelPricing.end_date.is_(None), ModelPricing.end_date > calculation_date),
            # The input model starts with the stored model name (prefix match)
            text(f"'{model_name}' ilike concat(model_name, '%%')")
        ).order_by(
            # Longest prefix first
            func.length(ModelPricing.model_name).desc(),
            ModelPricing.effective_date.desc()
        ).limit(1)
        
        result = await db.execute(query)
        pricing = result.scalar_one_or_none()
        
        if pricing:
            if pricing.model_name != model_name:
                logger.debug(f"Prefix match: '{model_name}' matched with '{pricing.model_name}'")
            
            return {
                'input_price': pricing.input_token_price,
                'output_price': pricing.output_token_price,
                'cached_price': pricing.cached_token_price,
                'currency': pricing.currency,
                'effective_date': pricing.effective_date.isoformat(),
                'end_date': pricing.end_date.isoformat() if pricing.end_date else None,
            }
        
        return None
    
    @staticmethod
    async def _get_provider_fallback_pricing_db(db: AsyncSession, provider_name: str, calculation_date: datetime) -> Optional[Dict[str, Any]]:
        """Get provider fallback pricing from database"""
        query = select(FallbackPricing).where(
            FallbackPricing.provider_name == provider_name,
            FallbackPricing.fallback_type == 'provider_default',
            FallbackPricing.effective_date <= calculation_date,
            or_(FallbackPricing.end_date.is_(None), FallbackPricing.end_date > calculation_date)
        ).order_by(FallbackPricing.effective_date.desc()).limit(1)
        
        result = await db.execute(query)
        fallback = result.scalar_one_or_none()
        
        if fallback:
            return {
                'input_price': fallback.input_token_price,
                'output_price': fallback.output_token_price,
                'cached_price': fallback.cached_token_price,
                'currency': 'USD',
                'effective_date': fallback.effective_date.isoformat(),
                'end_date': fallback.end_date.isoformat() if fallback.end_date else None,
            }
        return None
    
    @staticmethod
    async def _get_global_fallback_pricing_db(db: AsyncSession, calculation_date: datetime) -> Optional[Dict[str, Any]]:
        """Get global fallback pricing from database"""
        query = select(FallbackPricing).where(
            FallbackPricing.fallback_type == 'global_default',
            FallbackPricing.effective_date <= calculation_date,
            or_(FallbackPricing.end_date.is_(None), FallbackPricing.end_date > calculation_date)
        ).order_by(FallbackPricing.effective_date.desc()).limit(1)
        
        result = await db.execute(query)
        fallback = result.scalar_one_or_none()
        
        if fallback:
            return {
                'input_price': fallback.input_token_price,
                'output_price': fallback.output_token_price,
                'cached_price': fallback.cached_token_price,
                'currency': 'USD',
                'effective_date': fallback.effective_date.isoformat(),
                'end_date': fallback.end_date.isoformat() if fallback.end_date else None,
            }
        return None

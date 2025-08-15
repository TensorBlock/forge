import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher

@dataclass
class ModelMatch:
    """Represents a model match with confidence score"""
    matched_model: str
    confidence: float
    match_type: str  # 'exact', 'normalized', 'prefix', 'fuzzy'
    normalized_query: str
    normalized_match: str

class ModelNameMatcher:
    """
    Advanced model name matching algorithm with support for:
    - Date format conversion (@YYYYMMDD <-> -YYYY-MM-DD)
    - Prefix matching with longest match priority
    - Fuzzy matching for typos and variations
    - Model family grouping and versioning
    """
    
    def __init__(self, available_models: List[str]):
        self.available_models = available_models
        self.normalized_models = {self._normalize_model_name(model): model for model in available_models}
        self.model_families = self._build_model_families()
    
    def _normalize_model_name(self, model_name: str) -> str:
        """
        Normalize model names for better matching:
        - Convert @ date separators to -
        - Standardize date formats
        - Remove extra spaces/hyphens
        """
        normalized = model_name.lower().strip()
        
        # Handle @ date format conversion: gpt-4.1-mini@2025-04-14 -> gpt-4.1-mini-2025-04-14
        if '@' in normalized:
            parts = normalized.split('@')
            if len(parts) == 2:
                base_model, date_part = parts
                # Convert YYYYMMDD to YYYY-MM-DD if needed
                date_part = self._normalize_date_format(date_part)
                normalized = f"{base_model}-{date_part}"
        
        # Standardize separators
        normalized = re.sub(r'[_\s]+', '-', normalized)
        normalized = re.sub(r'-+', '-', normalized)  # Remove duplicate hyphens
        
        return normalized
    
    def _normalize_date_format(self, date_str: str) -> str:
        """Convert various date formats to YYYY-MM-DD"""
        date_str = date_str.strip()
        
        # YYYYMMDD -> YYYY-MM-DD
        if re.match(r'^\d{8}$', date_str):
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        # YYYY-MM-DD (already correct)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
            
        # YYYY/MM/DD -> YYYY-MM-DD
        if re.match(r'^\d{4}/\d{2}/\d{2}$', date_str):
            return date_str.replace('/', '-')
        
        return date_str  # Return as-is if no pattern matches
    
    def _build_model_families(self) -> Dict[str, List[str]]:
        """Group models by family for better matching"""
        families = {}
        
        for model in self.available_models:
            # Extract base model name (before version/date info)
            base = re.split(r'[-_]\d', model)[0]  # Split at first digit after separator
            base = re.sub(r'-(latest|preview)$', '', base)  # Remove common suffixes
            
            if base not in families:
                families[base] = []
            families[base].append(model)
        
        return families
    
    def find_best_match(self, query_model: str, min_confidence: float = 0.6) -> Optional[ModelMatch]:
        """
        Find the best matching model using multiple strategies:
        1. Exact match
        2. Normalized exact match
        3. Prefix matching (longest first)
        4. Family-based fuzzy matching
        """
        
        # Strategy 1: Exact match
        if query_model in self.available_models:
            return ModelMatch(
                matched_model=query_model,
                confidence=1.0,
                match_type='exact',
                normalized_query=query_model,
                normalized_match=query_model
            )
        
        normalized_query = self._normalize_model_name(query_model)
        
        # Strategy 2: Normalized exact match
        if normalized_query in self.normalized_models:
            matched_model = self.normalized_models[normalized_query]
            return ModelMatch(
                matched_model=matched_model,
                confidence=0.95,
                match_type='normalized',
                normalized_query=normalized_query,
                normalized_match=normalized_query
            )
        
        # Strategy 3: Prefix matching (longest match first)
        prefix_matches = self._find_prefix_matches(normalized_query)
        if prefix_matches:
            best_prefix = max(prefix_matches, key=lambda x: (len(x[1]), x[2]))  # Longest match, highest confidence
            return ModelMatch(
                matched_model=best_prefix[0],
                confidence=best_prefix[2],
                match_type='prefix',
                normalized_query=normalized_query,
                normalized_match=best_prefix[1]
            )
        
        # Strategy 4: Fuzzy matching within model families
        fuzzy_match = self._find_fuzzy_match(normalized_query, min_confidence)
        if fuzzy_match:
            return fuzzy_match
        
        return None
    
    def _find_prefix_matches(self, normalized_query: str) -> List[Tuple[str, str, float]]:
        """Find models that match as prefixes, with confidence scoring"""
        matches = []
        
        for normalized_model, original_model in self.normalized_models.items():
            # Check if query starts with stored model (database models are prefixes)
            if normalized_query.startswith(normalized_model):
                prefix_len = len(normalized_model)
                query_len = len(normalized_query)
                
                # Calculate confidence based on how much of the query is matched
                confidence = min(0.9, prefix_len / query_len * 0.9)
                
                # Bonus for exact word boundaries
                if query_len == prefix_len or normalized_query[prefix_len] in '-_.':
                    confidence += 0.05
                
                matches.append((original_model, normalized_model, confidence))
            
            # Also check reverse: if stored model starts with query (query is prefix of stored model)
            elif normalized_model.startswith(normalized_query):
                prefix_len = len(normalized_query)
                model_len = len(normalized_model)
                
                # Lower confidence for partial matches
                confidence = min(0.85, prefix_len / model_len * 0.8)
                
                # Bonus for exact word boundaries
                if model_len == prefix_len or normalized_model[prefix_len] in '-_.':
                    confidence += 0.05
                
                matches.append((original_model, normalized_model, confidence))
        
        return matches
    
    def _find_fuzzy_match(self, normalized_query: str, min_confidence: float) -> Optional[ModelMatch]:
        """Find best fuzzy match using sequence similarity"""
        best_match = None
        best_confidence = 0.0
        
        # First try within same model family
        query_base = re.split(r'[-_]\d', normalized_query)[0]
        
        if query_base in self.model_families:
            for candidate in self.model_families[query_base]:
                normalized_candidate = self._normalize_model_name(candidate)
                confidence = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
                
                if confidence > best_confidence and confidence >= min_confidence:
                    best_confidence = confidence
                    best_match = ModelMatch(
                        matched_model=candidate,
                        confidence=confidence,
                        match_type='fuzzy',
                        normalized_query=normalized_query,
                        normalized_match=normalized_candidate
                    )
        
        # If no good family match, try all models with higher threshold
        if not best_match:
            high_threshold = max(min_confidence, 0.8)
            for normalized_model, original_model in self.normalized_models.items():
                confidence = SequenceMatcher(None, normalized_query, normalized_model).ratio()
                
                if confidence > best_confidence and confidence >= high_threshold:
                    best_confidence = confidence
                    best_match = ModelMatch(
                        matched_model=original_model,
                        confidence=confidence,
                        match_type='fuzzy',
                        normalized_query=normalized_query,
                        normalized_match=normalized_model
                    )
        
        return best_match
    
    def find_all_matches(self, query_model: str, min_confidence: float = 0.6, limit: int = 5) -> List[ModelMatch]:
        """Find all possible matches sorted by confidence"""
        matches = []
        normalized_query = self._normalize_model_name(query_model)
        
        # Check exact match first
        if query_model in self.available_models:
            matches.append(ModelMatch(
                matched_model=query_model,
                confidence=1.0,
                match_type='exact',
                normalized_query=query_model,
                normalized_match=query_model
            ))
            return matches
        
        # Find all prefix matches
        prefix_matches = self._find_prefix_matches(normalized_query)
        for original_model, normalized_model, confidence in prefix_matches:
            if confidence >= min_confidence:
                matches.append(ModelMatch(
                    matched_model=original_model,
                    confidence=confidence,
                    match_type='prefix',
                    normalized_query=normalized_query,
                    normalized_match=normalized_model
                ))
        
        # Find fuzzy matches if we don't have enough good matches
        if len(matches) < limit:
            for normalized_model, original_model in self.normalized_models.items():
                confidence = SequenceMatcher(None, normalized_query, normalized_model).ratio()
                
                if confidence >= min_confidence:
                    # Check if we already have this match
                    if not any(m.matched_model == original_model for m in matches):
                        matches.append(ModelMatch(
                            matched_model=original_model,
                            confidence=confidence,
                            match_type='fuzzy',
                            normalized_query=normalized_query,
                            normalized_match=normalized_model
                        ))
        
        # Sort by confidence (descending) and return top matches
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches[:limit]

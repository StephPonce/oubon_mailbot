"""
SEARCH RELEVANCE FILTER
=======================

Post-processing filter to ensure product results match search intent.

Features:
1. Title similarity scoring (fuzzy matching)
2. Category validation
3. Negative keyword filtering
4. Semantic relevance scoring

Fixes the problem where "fung's kitchen" returns "Solar Panel Gland Box"
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from difflib import SequenceMatcher
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class RelevanceScore:
    """Relevance scoring result for a product."""
    product_id: str
    product_title: str
    query: str
    title_similarity: float  # 0-1 word overlap
    keyword_match_ratio: float  # 0-1 important keywords found
    category_match: bool
    has_negative_keywords: bool
    final_score: float  # 0-100 overall relevance
    is_relevant: bool
    rejection_reason: Optional[str] = None


class SearchRelevanceFilter:
    """
    Filter and rank search results by relevance to query intent.
    
    Usage:
        filter = SearchRelevanceFilter()
        
        # Filter single product
        if filter.is_relevant(product_title, query):
            # Keep product
            
        # Filter and rank list of products
        relevant_products = filter.filter_products(products, query)
    """
    
    # Words to ignore when matching (common but not meaningful)
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'new', 'hot', 'best', 'top', 'sale', 'free', 'shipping', 'pc', 'pcs',
        'set', 'pack', 'lot', 'wholesale', 'retail', 'piece', 'pieces'
    }
    
    # Negative keywords by category (if product has these but query doesn't, likely wrong)
    CATEGORY_NEGATIVE_KEYWORDS = {
        'electronics': {'doll', 'toy', 'dress', 'shirt', 'pants', 'shoes', 'food', 'beauty'},
        'kitchen': {'electronics', 'phone', 'computer', 'cable', 'doll', 'toy', 'car'},
        'smart_home': {'doll', 'toy', 'dress', 'shirt', 'pants', 'shoes', 'beauty', 'food'},
        'fitness': {'doll', 'toy', 'dress', 'cable', 'phone', 'computer', 'beauty'},
        'home_decor': {'electronics', 'phone', 'computer', 'car', 'tool', 'fitness'},
    }
    
    # Strong negative keywords (almost always wrong if present)
    GLOBAL_NEGATIVE_KEYWORDS = {
        'adult', 'sexy', '18+', 'erotic', 'replica', 'fake', 'counterfeit',
        'wholesale only', 'minimum order', 'dropship inquiry'
    }
    
    # Category detection patterns
    CATEGORY_PATTERNS = {
        'electronics': ['smart', 'wifi', 'bluetooth', 'led', 'usb', 'sensor', 'digital', 'wireless', 'remote'],
        'kitchen': ['kitchen', 'cooking', 'chef', 'food', 'knife', 'pot', 'pan', 'utensil', 'spatula', 'mixer'],
        'smart_home': ['smart', 'home', 'automation', 'alexa', 'google', 'zigbee', 'wifi', 'sensor', 'security'],
        'fitness': ['fitness', 'gym', 'workout', 'exercise', 'sport', 'yoga', 'running', 'weight', 'muscle'],
        'home_decor': ['decor', 'decoration', 'wall', 'art', 'frame', 'vase', 'lamp', 'furniture', 'rug'],
    }

    def __init__(
        self,
        min_relevance_score: float = 30.0,
        min_keyword_match: float = 0.3,
        strict_mode: bool = False
    ):
        """
        Initialize relevance filter.
        
        Args:
            min_relevance_score: Minimum score (0-100) to consider relevant
            min_keyword_match: Minimum ratio of query keywords in title
            strict_mode: If True, require higher thresholds
        """
        self.min_relevance_score = min_relevance_score
        self.min_keyword_match = min_keyword_match
        self.strict_mode = strict_mode
        
        if strict_mode:
            self.min_relevance_score = max(50.0, min_relevance_score)
            self.min_keyword_match = max(0.5, min_keyword_match)

    def tokenize(self, text: str) -> Set[str]:
        """
        Tokenize text into meaningful words.
        
        Removes stopwords, numbers, and short words.
        """
        if not text:
            return set()
            
        # Lowercase and split
        words = re.findall(r'[a-z]+', text.lower())
        
        # Filter
        meaningful = {
            w for w in words 
            if len(w) > 2 and w not in self.STOPWORDS
        }
        
        return meaningful

    def calculate_title_similarity(self, title: str, query: str) -> float:
        """
        Calculate word-based similarity between title and query.
        
        Returns: 0-1 similarity score
        """
        title_words = self.tokenize(title)
        query_words = self.tokenize(query)
        
        if not query_words:
            return 0.5  # Can't judge without query words
            
        if not title_words:
            return 0.0
        
        # Calculate overlap
        overlap = title_words & query_words
        
        # Jaccard similarity
        union = title_words | query_words
        jaccard = len(overlap) / len(union) if union else 0
        
        # Also check if query words are in title (more important)
        query_coverage = len(overlap) / len(query_words)
        
        # Weighted combination
        return 0.4 * jaccard + 0.6 * query_coverage

    def calculate_keyword_match(self, title: str, query: str) -> Tuple[float, List[str]]:
        """
        Check how many important query keywords appear in title.
        
        Returns: (match_ratio, matched_keywords)
        """
        title_lower = title.lower()
        query_words = self.tokenize(query)
        
        matched = []
        for word in query_words:
            if word in title_lower:
                matched.append(word)
        
        ratio = len(matched) / len(query_words) if query_words else 0
        return ratio, matched

    def detect_category(self, text: str) -> Optional[str]:
        """Detect likely product category from text."""
        text_lower = text.lower()
        
        scores = {}
        for category, patterns in self.CATEGORY_PATTERNS.items():
            score = sum(1 for p in patterns if p in text_lower)
            if score > 0:
                scores[category] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None

    def has_negative_keywords(
        self,
        title: str,
        query: str,
        category: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if title contains negative keywords.
        
        Args:
            title: Product title
            query: Search query
            category: Detected category (optional)
            
        Returns: (has_negative, list_of_negative_keywords_found)
        """
        title_lower = title.lower()
        query_lower = query.lower()
        found = []
        
        # Check global negatives
        for neg in self.GLOBAL_NEGATIVE_KEYWORDS:
            if neg in title_lower and neg not in query_lower:
                found.append(neg)
        
        # Check category-specific negatives
        if category and category in self.CATEGORY_NEGATIVE_KEYWORDS:
            for neg in self.CATEGORY_NEGATIVE_KEYWORDS[category]:
                if neg in title_lower and neg not in query_lower:
                    found.append(neg)
        
        return len(found) > 0, found

    def score_product(
        self,
        product_title: str,
        query: str,
        product_id: str = "",
        product_category: Optional[str] = None
    ) -> RelevanceScore:
        """
        Score a product's relevance to the search query.
        
        Returns: RelevanceScore with detailed breakdown
        """
        # Calculate components
        title_similarity = self.calculate_title_similarity(product_title, query)
        keyword_ratio, matched_keywords = self.calculate_keyword_match(product_title, query)
        
        # Detect categories
        query_category = product_category or self.detect_category(query)
        title_category = self.detect_category(product_title)
        category_match = (query_category == title_category) if query_category else True
        
        # Check negatives
        has_negative, negative_keywords = self.has_negative_keywords(
            product_title, query, query_category
        )
        
        # Calculate final score (0-100)
        final_score = 0.0
        
        # Title similarity (40 points max)
        final_score += title_similarity * 40
        
        # Keyword match (40 points max)
        final_score += keyword_ratio * 40
        
        # Category match (10 points)
        if category_match:
            final_score += 10
        
        # Negative keywords penalty (-20 points each)
        if has_negative:
            final_score -= len(negative_keywords) * 20
        
        # Bonus for exact phrase match
        if query.lower() in product_title.lower():
            final_score += 10
        
        # Clamp to 0-100
        final_score = max(0, min(100, final_score))
        
        # Determine if relevant
        is_relevant = (
            final_score >= self.min_relevance_score and
            keyword_ratio >= self.min_keyword_match and
            not has_negative
        )
        
        # Determine rejection reason
        rejection_reason = None
        if not is_relevant:
            if has_negative:
                rejection_reason = f"Contains negative keywords: {negative_keywords}"
            elif keyword_ratio < self.min_keyword_match:
                rejection_reason = f"Low keyword match: {keyword_ratio:.0%} (need {self.min_keyword_match:.0%})"
            elif final_score < self.min_relevance_score:
                rejection_reason = f"Low relevance score: {final_score:.0f} (need {self.min_relevance_score:.0f})"
        
        return RelevanceScore(
            product_id=product_id,
            product_title=product_title,
            query=query,
            title_similarity=title_similarity,
            keyword_match_ratio=keyword_ratio,
            category_match=category_match,
            has_negative_keywords=has_negative,
            final_score=final_score,
            is_relevant=is_relevant,
            rejection_reason=rejection_reason
        )

    def is_relevant(
        self,
        product_title: str,
        query: str,
        category: Optional[str] = None
    ) -> bool:
        """
        Quick check if a product is relevant to query.
        
        Args:
            product_title: Product title to check
            query: Search query
            category: Optional category hint
            
        Returns: True if product is relevant
        """
        score = self.score_product(product_title, query, product_category=category)
        return score.is_relevant

    def filter_products(
        self,
        products: List[Dict[str, Any]],
        query: str,
        title_key: str = "name",
        id_key: str = "id",
        category: Optional[str] = None,
        return_scores: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter and rank products by relevance.
        
        Args:
            products: List of product dicts
            query: Search query
            title_key: Key for product title in dict
            id_key: Key for product ID in dict
            category: Optional category hint
            return_scores: If True, add relevance_score to each product
            
        Returns: Filtered and sorted list of relevant products
        """
        scored = []
        
        for product in products:
            title = product.get(title_key, "")
            product_id = product.get(id_key, "")
            
            score = self.score_product(
                product_title=title,
                query=query,
                product_id=str(product_id),
                product_category=category
            )
            
            if score.is_relevant:
                if return_scores:
                    product = dict(product)  # Copy
                    product['relevance_score'] = score.final_score
                    product['relevance_details'] = {
                        'title_similarity': score.title_similarity,
                        'keyword_match': score.keyword_match_ratio,
                        'category_match': score.category_match
                    }
                scored.append((score.final_score, product))
            else:
                logger.debug(
                    f"Filtered out '{title[:50]}...' - {score.rejection_reason}"
                )
        
        # Sort by score (highest first)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return just the products
        filtered = [p for _, p in scored]
        
        logger.info(
            f"Relevance filter: {len(filtered)}/{len(products)} products passed "
            f"for query '{query}'"
        )
        
        return filtered

    def filter_with_fallback(
        self,
        products: List[Dict[str, Any]],
        query: str,
        title_key: str = "name",
        min_results: int = 3,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Filter products with fallback to relaxed thresholds.
        
        If strict filtering returns too few results, gradually relax
        thresholds to ensure minimum results.
        
        Args:
            products: Products to filter
            query: Search query
            title_key: Key for title in product dict
            min_results: Minimum number of results to return
            **kwargs: Additional args for filter_products
            
        Returns: At least min_results products (or all if less available)
        """
        # Try strict filtering first
        filtered = self.filter_products(products, query, title_key, **kwargs)
        
        if len(filtered) >= min_results:
            return filtered
        
        # Gradually relax thresholds
        thresholds = [
            (25.0, 0.2),  # Relaxed
            (15.0, 0.1),  # Very relaxed
            (0.0, 0.0),   # Accept anything
        ]
        
        for min_score, min_keyword in thresholds:
            relaxed_filter = SearchRelevanceFilter(
                min_relevance_score=min_score,
                min_keyword_match=min_keyword
            )
            filtered = relaxed_filter.filter_products(
                products, query, title_key, **kwargs
            )
            
            if len(filtered) >= min_results:
                logger.warning(
                    f"Relaxed relevance thresholds to score={min_score}, "
                    f"keyword={min_keyword} to get {len(filtered)} results"
                )
                return filtered
        
        # Return whatever we have
        return filtered[:min_results] if filtered else products[:min_results]


class QueryOptimizer:
    """
    Optimize search queries for better results.
    
    Features:
    - Remove noise words
    - Extract core product terms
    - Generate alternative queries
    """
    
    # Words that indicate query intent but not product name
    INTENT_WORDS = {
        'best', 'top', 'cheap', 'affordable', 'premium', 'quality',
        'trending', 'popular', 'new', 'latest', 'hot', '2024', '2025',
        'buy', 'find', 'get', 'show', 'search', 'looking',
        'christmas', 'holiday', 'gift', 'sale', 'deal', 'discount'
    }
    
    # Time-related words to remove
    TIME_WORDS = {
        'hours', 'today', 'now', 'tonight', 'tomorrow', 'yesterday',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'saturday', 'sunday', 'morning', 'afternoon', 'evening', 'night'
    }
    
    # Location words to remove
    LOCATION_WORDS = {
        'near', 'nearby', 'local', 'online', 'store', 'shop',
        'amazon', 'walmart', 'target', 'costco'
    }

    @classmethod
    def optimize_query(cls, query: str) -> str:
        """
        Clean and optimize a search query.
        
        Removes intent words, time references, etc.
        """
        words = query.lower().split()
        
        # Remove noise
        cleaned = []
        for word in words:
            word = re.sub(r'[^\w\s]', '', word)  # Remove punctuation
            if (word and 
                len(word) > 2 and
                word not in cls.INTENT_WORDS and
                word not in cls.TIME_WORDS and
                word not in cls.LOCATION_WORDS):
                cleaned.append(word)
        
        optimized = ' '.join(cleaned)
        
        if not optimized or len(optimized) < 3:
            # If too aggressive, return original without punctuation
            return re.sub(r'[^\w\s]', '', query)
        
        return optimized

    @classmethod
    def generate_alternatives(cls, query: str) -> List[str]:
        """
        Generate alternative search queries.
        
        Useful for broadening search if initial query returns few results.
        """
        alternatives = []
        base = cls.optimize_query(query)
        
        if base:
            alternatives.append(base)
        
        words = base.split()
        
        # Single important words
        for word in words:
            if len(word) > 4:  # Only longer words
                alternatives.append(word)
        
        # Pairs of words
        if len(words) >= 2:
            for i in range(len(words) - 1):
                pair = f"{words[i]} {words[i+1]}"
                alternatives.append(pair)
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for alt in alternatives:
            if alt not in seen:
                seen.add(alt)
                unique.append(alt)
        
        return unique


# Convenience functions

def filter_search_results(
    products: List[Dict],
    query: str,
    title_key: str = "name",
    min_results: int = 3
) -> List[Dict]:
    """
    Quick function to filter search results.
    
    Example:
        products = await aliexpress.search("smart kitchen gadget")
        relevant = filter_search_results(products, "smart kitchen gadget")
    """
    filter_instance = SearchRelevanceFilter()
    return filter_instance.filter_with_fallback(
        products, query, title_key, min_results
    )


def optimize_search_query(query: str) -> str:
    """
    Quick function to optimize a search query.
    
    Example:
        optimized = optimize_search_query("best smart home christmas deals 2024")
        # Returns: "smart home"
    """
    return QueryOptimizer.optimize_query(query)


def get_search_alternatives(query: str) -> List[str]:
    """
    Get alternative search queries.
    
    Example:
        alts = get_search_alternatives("smart kitchen gadget")
        # Returns: ["smart kitchen gadget", "smart kitchen", "kitchen gadget", "smart", "kitchen", "gadget"]
    """
    return QueryOptimizer.generate_alternatives(query)

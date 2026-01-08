"""
Oi Response Validator - Hallucination Detection

Validates AI responses to catch fabricated data before it reaches users.
Checks if claims in the response are backed by actual context data.

Author: OspraOS
Date: December 2024
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool
    severity: str = "low"  # "low", "medium", "high"
    warnings: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    flagged_claims: List[str] = field(default_factory=list)


class ResponseValidator:
    """
    Validates Oi responses to catch hallucinations.
    
    Checks for:
    1. Revenue/money claims without metrics data
    2. Order counts without order data
    3. Product names/stats without product data
    4. Trending claims without intelligence engine
    5. Email stats without email connection
    """
    
    # Patterns that indicate data claims
    MONEY_PATTERN = r'\$[\d,]+(?:\.\d{2})?'
    PERCENT_PATTERN = r'\d+(?:\.\d+)?%'
    ORDER_PATTERN = r'(\d+)\s*orders?'
    PRODUCT_COUNT_PATTERN = r'(\d+)\s*products?'
    REVENUE_KEYWORDS = ['revenue', 'sales', 'earned', 'made', 'profit', 'income']
    METRICS_KEYWORDS = ['conversion', 'aov', 'average order', 'visitors', 'traffic']
    TRENDING_KEYWORDS = ['trending', 'hot', 'viral', 'rising', 'popular']
    EMAIL_KEYWORDS = ['unread', 'emails', 'inbox', 'replied', 'auto-replied']
    
    def validate(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate a response against available context.
        
        Args:
            response: The AI's response text
            context: The context data that was available
            
        Returns:
            ValidationResult with validity status and warnings
        """
        warnings = []
        missing_data = []
        flagged_claims = []
        
        # Get connection status
        status = context.get("connection_status", {})
        
        # Check 1: Money claims without metrics
        if self._has_money_claims(response):
            if not status.get("has_metrics"):
                warnings.append("Response contains dollar amounts but no metrics data is connected")
                missing_data.append("store_metrics")
                flagged_claims.extend(self._extract_money_claims(response))
        
        # Check 2: Order counts without order data
        if self._mentions_orders(response):
            if not status.get("has_orders"):
                warnings.append("Response mentions orders but no order data is connected")
                missing_data.append("orders")
                flagged_claims.extend(self._extract_order_claims(response))
        
        # Check 3: Specific product stats without product data
        if self._has_product_stats(response):
            if not status.get("has_products") or not self._verify_products_in_context(response, context):
                warnings.append("Response contains product statistics without verified product data")
                missing_data.append("products")
        
        # Check 4: Trending claims without intelligence engine
        if self._mentions_trending(response):
            if not status.get("has_trending"):
                warnings.append("Response mentions trending products but Intelligence Engine is not connected")
                missing_data.append("trending")
        
        # Check 5: Email stats without email connection
        if self._mentions_email_stats(response):
            if not status.get("has_email"):
                warnings.append("Response contains email statistics but no email is connected")
                missing_data.append("email")
        
        # Check 6: Specific percentages without data source
        if self._has_specific_percentages(response):
            if not status.get("has_metrics") and not status.get("has_trending"):
                warnings.append("Response contains specific percentages without data backing")
                flagged_claims.extend(self._extract_percentage_claims(response))
        
        # Determine severity
        severity = self._calculate_severity(warnings, flagged_claims)
        
        # Is valid if no warnings or only low severity
        is_valid = len(warnings) == 0 or severity == "low"
        
        if warnings:
            logger.warning(f"Validation warnings: {warnings}")
        
        return ValidationResult(
            is_valid=is_valid,
            severity=severity,
            warnings=warnings,
            missing_data=missing_data,
            flagged_claims=flagged_claims
        )
    
    def _has_money_claims(self, response: str) -> bool:
        """Check if response contains dollar amounts."""
        return bool(re.search(self.MONEY_PATTERN, response))
    
    def _extract_money_claims(self, response: str) -> List[str]:
        """Extract all money claims from response."""
        return re.findall(self.MONEY_PATTERN, response)
    
    def _mentions_orders(self, response: str) -> bool:
        """Check if response mentions specific order counts."""
        return bool(re.search(self.ORDER_PATTERN, response, re.IGNORECASE))
    
    def _extract_order_claims(self, response: str) -> List[str]:
        """Extract order count claims."""
        matches = re.findall(self.ORDER_PATTERN, response, re.IGNORECASE)
        return [f"{m} orders" for m in matches]
    
    def _has_product_stats(self, response: str) -> bool:
        """Check if response contains specific product statistics."""
        response_lower = response.lower()
        
        # Check for product counts
        if re.search(self.PRODUCT_COUNT_PATTERN, response, re.IGNORECASE):
            return True
        
        # Check for revenue/metrics keywords combined with product names
        for keyword in self.REVENUE_KEYWORDS + self.METRICS_KEYWORDS:
            if keyword in response_lower:
                return True
        
        return False
    
    def _verify_products_in_context(self, response: str, context: Dict[str, Any]) -> bool:
        """Check if products mentioned exist in context."""
        products = context.get("products", [])
        
        if not products or not isinstance(products, list):
            return False
        
        # Get product names from context
        product_names = set()
        for p in products:
            if isinstance(p, dict) and "name" in p:
                product_names.add(p["name"].lower())
        
        if not product_names:
            return False
        
        # Check if any mentioned products are in our data
        response_lower = response.lower()
        for name in product_names:
            if name in response_lower:
                return True
        
        return False
    
    def _mentions_trending(self, response: str) -> bool:
        """Check if response mentions trending/hot products."""
        response_lower = response.lower()
        return any(kw in response_lower for kw in self.TRENDING_KEYWORDS)
    
    def _mentions_email_stats(self, response: str) -> bool:
        """Check if response mentions email statistics."""
        response_lower = response.lower()
        return any(kw in response_lower for kw in self.EMAIL_KEYWORDS)
    
    def _has_specific_percentages(self, response: str) -> bool:
        """Check if response contains specific percentage claims."""
        # Match percentages that aren't just "100%" or "0%"
        matches = re.findall(self.PERCENT_PATTERN, response)
        # Filter out common non-specific percentages
        significant = [m for m in matches if m not in ['0%', '100%', '50%']]
        return len(significant) > 0
    
    def _extract_percentage_claims(self, response: str) -> List[str]:
        """Extract percentage claims."""
        return re.findall(self.PERCENT_PATTERN, response)
    
    def _calculate_severity(
        self,
        warnings: List[str],
        flagged_claims: List[str]
    ) -> str:
        """Calculate severity of validation issues."""
        if not warnings:
            return "low"
        
        # High severity: Multiple data types fabricated or specific numbers
        if len(warnings) >= 3:
            return "high"
        
        if len(flagged_claims) >= 5:
            return "high"
        
        # Medium severity: Some data fabrication
        if len(warnings) >= 2 or len(flagged_claims) >= 2:
            return "medium"
        
        return "low"


# Singleton for easy access
_validator_instance = None

def get_response_validator() -> ResponseValidator:
    """Get or create the response validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ResponseValidator()
    return _validator_instance

"""
OI NATURAL LANGUAGE COMMAND PARSER
==================================

Transforms natural language into executable actions.

Examples:
- "Deploy the top 3 products" → deploy_product x3
- "Pause all ads under 2% CTR" → pause_ad with filter
- "Increase budget on best ad by 20%" → adjust_budget +20%
- "What's trending?" → query (not an action)

Architecture:
1. Intent Classification - What does the user want to do?
2. Entity Extraction - What objects/values are mentioned?
3. Action Mapping - Convert to executable action(s)
4. Confidence Scoring - How sure are we?

Uses Claude for complex parsing, regex for simple patterns.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """High-level intent categories."""
    # Actions (executable)
    DEPLOY = "deploy"
    PAUSE = "pause"
    RESUME = "resume"
    ADJUST_BUDGET = "adjust_budget"
    ADJUST_PRICE = "adjust_price"
    CREATE_AD = "create_ad"
    REORDER = "reorder"
    DROP_PRODUCT = "drop_product"
    
    # Queries (informational)
    QUERY_TRENDING = "query_trending"
    QUERY_PERFORMANCE = "query_performance"
    QUERY_STATUS = "query_status"
    QUERY_RECOMMENDATION = "query_recommendation"
    
    # Meta
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ExtractedEntity:
    """An entity extracted from the command."""
    entity_type: str  # product, ad, store, number, percentage, timeframe
    value: Any
    raw_text: str
    confidence: float = 1.0


@dataclass
class ParsedCommand:
    """Result of parsing a natural language command."""
    original_text: str
    intent: IntentType
    entities: List[ExtractedEntity] = field(default_factory=list)
    action_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    is_executable: bool = False
    requires_confirmation: bool = True
    clarification_needed: Optional[str] = None
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "intent": self.intent.value,
            "entities": [
                {
                    "type": e.entity_type,
                    "value": e.value,
                    "raw": e.raw_text,
                    "confidence": e.confidence
                }
                for e in self.entities
            ],
            "action_type": self.action_type,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "is_executable": self.is_executable,
            "requires_confirmation": self.requires_confirmation,
            "clarification_needed": self.clarification_needed,
            "suggested_actions": self.suggested_actions
        }


class NLCommandParser:
    """
    Natural Language Command Parser for Oi.
    
    Converts user commands into structured actions.
    """
    
    # Intent patterns (regex-based for speed)
    INTENT_PATTERNS = {
        IntentType.DEPLOY: [
            r'\b(deploy|publish|push|launch|add to store|list)\b',
            r'\b(put .* on shopify|send to store)\b',
        ],
        IntentType.PAUSE: [
            r'\b(pause|stop|halt|disable|turn off)\b',
        ],
        IntentType.RESUME: [
            r'\b(resume|restart|unpause|enable|turn on|reactivate)\b',
        ],
        IntentType.ADJUST_BUDGET: [
            r'\b(increase|decrease|raise|lower|boost|cut|change|adjust).*(budget|spend|spending)\b',
            r'\b(budget|spend).*(increase|decrease|raise|lower|boost|cut|change|adjust)\b',
            r'\bset budget\b',
        ],
        IntentType.ADJUST_PRICE: [
            r'\b(increase|decrease|raise|lower|change|adjust).*(price|pricing|cost)\b',
            r'\b(price|pricing).*(increase|decrease|raise|lower|change|adjust)\b',
            r'\bset price\b',
        ],
        IntentType.CREATE_AD: [
            r'\b(create|make|start|launch|run).*(ad|campaign|advertisement)\b',
            r'\b(ad|campaign).*(create|make|start|launch)\b',
        ],
        IntentType.REORDER: [
            r'\b(reorder|restock|order more|replenish)\b',
        ],
        IntentType.DROP_PRODUCT: [
            r'\b(drop|remove|delete|discontinue|delist)\b.*\b(product|item)\b',
        ],
        IntentType.QUERY_TRENDING: [
            r'\b(what\'?s?|show|find).*(trending|hot|popular|viral)\b',
            r'\btrending\b',
            r'\btop products\b',
        ],
        IntentType.QUERY_PERFORMANCE: [
            r'\b(how|what).*(performing|performance|doing|going)\b',
            r'\b(show|get).*(stats|statistics|metrics|analytics)\b',
        ],
        IntentType.QUERY_STATUS: [
            r'\b(status|state|health)\b',
            r'\bwhat\'?s the status\b',
        ],
        IntentType.QUERY_RECOMMENDATION: [
            r'\b(recommend|suggest|advice|should i|what should)\b',
        ],
        IntentType.HELP: [
            r'\b(help|how do i|what can you|commands)\b',
        ],
    }
    
    # Entity patterns
    ENTITY_PATTERNS = {
        "number": r'\b(\d+)\b',
        "percentage": r'\b(\d+(?:\.\d+)?)\s*%',
        "money": r'\$\s*(\d+(?:\.\d+)?)',
        "top_n": r'\btop\s*(\d+)\b',
        "all": r'\ball\b',
        "best": r'\b(best|top|highest|most)\b',
        "worst": r'\b(worst|lowest|bottom|least)\b',
        "timeframe_days": r'\b(\d+)\s*days?\b',
        "timeframe_hours": r'\b(\d+)\s*hours?\b',
        "comparison": r'\b(under|below|less than|over|above|more than|greater than)\s*(\d+(?:\.\d+)?)\s*%?',
    }
    
    # Action type mapping
    INTENT_TO_ACTION = {
        IntentType.DEPLOY: "deploy_product",
        IntentType.PAUSE: "pause_ad",
        IntentType.RESUME: "resume_ad",
        IntentType.ADJUST_BUDGET: "adjust_budget",
        IntentType.ADJUST_PRICE: "adjust_price",
        IntentType.CREATE_AD: "create_ad_campaign",
        IntentType.REORDER: "reorder_inventory",
        IntentType.DROP_PRODUCT: "drop_product",
    }
    
    def __init__(self):
        self.use_claude_for_complex = bool(os.getenv('ANTHROPIC_API_KEY'))
    
    def parse(self, text: str) -> ParsedCommand:
        """
        Parse a natural language command.
        
        Args:
            text: The user's command in natural language
        
        Returns:
            ParsedCommand with intent, entities, and action details
        """
        text = text.strip()
        
        # Step 1: Classify intent
        intent, intent_confidence = self._classify_intent(text)
        
        # Step 2: Extract entities
        entities = self._extract_entities(text)
        
        # Step 3: Build the parsed command
        parsed = ParsedCommand(
            original_text=text,
            intent=intent,
            entities=entities,
            confidence=intent_confidence
        )
        
        # Step 4: Map to action if executable
        if intent in self.INTENT_TO_ACTION:
            parsed.action_type = self.INTENT_TO_ACTION[intent]
            parsed.is_executable = True
            parsed.parameters = self._build_parameters(intent, entities, text)
            
            # Determine if confirmation needed
            parsed.requires_confirmation = self._needs_confirmation(intent, entities)
            
            # Build suggested actions
            parsed.suggested_actions = self._build_suggested_actions(parsed)
        
        # Step 5: Check if clarification needed
        parsed.clarification_needed = self._check_clarification(parsed)
        
        logger.info(f"[BRAIN] Parsed command: {intent.value} (confidence: {intent_confidence:.2f})")
        
        return parsed
    
    def _classify_intent(self, text: str) -> Tuple[IntentType, float]:
        """Classify the intent of the command."""
        text_lower = text.lower()
        
        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Simple scoring: more specific patterns = higher confidence
                    confidence = 0.7 + (len(pattern) / 100)  # Longer = more specific
                    confidence = min(confidence, 0.95)
                    
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
        
        return best_intent, best_confidence
    
    def _extract_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract entities from the command."""
        entities = []
        text_lower = text.lower()
        
        # Extract numbers
        for match in re.finditer(self.ENTITY_PATTERNS["number"], text):
            entities.append(ExtractedEntity(
                entity_type="number",
                value=int(match.group(1)),
                raw_text=match.group(0)
            ))
        
        # Extract percentages
        for match in re.finditer(self.ENTITY_PATTERNS["percentage"], text):
            entities.append(ExtractedEntity(
                entity_type="percentage",
                value=float(match.group(1)),
                raw_text=match.group(0)
            ))
        
        # Extract money amounts
        for match in re.finditer(self.ENTITY_PATTERNS["money"], text):
            entities.append(ExtractedEntity(
                entity_type="money",
                value=float(match.group(1)),
                raw_text=match.group(0)
            ))
        
        # Extract "top N"
        for match in re.finditer(self.ENTITY_PATTERNS["top_n"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="top_n",
                value=int(match.group(1)),
                raw_text=match.group(0)
            ))
        
        # Extract "all"
        if re.search(self.ENTITY_PATTERNS["all"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="scope",
                value="all",
                raw_text="all"
            ))
        
        # Extract "best/top" or "worst/bottom"
        if re.search(self.ENTITY_PATTERNS["best"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="ranking",
                value="best",
                raw_text=re.search(self.ENTITY_PATTERNS["best"], text_lower).group(0)
            ))
        elif re.search(self.ENTITY_PATTERNS["worst"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="ranking",
                value="worst",
                raw_text=re.search(self.ENTITY_PATTERNS["worst"], text_lower).group(0)
            ))
        
        # Extract comparisons (under 2%, above 50%, etc.)
        for match in re.finditer(self.ENTITY_PATTERNS["comparison"], text_lower):
            operator = match.group(1)
            value = float(match.group(2))
            
            # Normalize operator
            if operator in ["under", "below", "less than"]:
                op = "lt"
            else:
                op = "gt"
            
            entities.append(ExtractedEntity(
                entity_type="comparison",
                value={"operator": op, "value": value},
                raw_text=match.group(0)
            ))
        
        # Extract timeframes
        for match in re.finditer(self.ENTITY_PATTERNS["timeframe_days"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="timeframe",
                value={"days": int(match.group(1))},
                raw_text=match.group(0)
            ))
        
        for match in re.finditer(self.ENTITY_PATTERNS["timeframe_hours"], text_lower):
            entities.append(ExtractedEntity(
                entity_type="timeframe",
                value={"hours": int(match.group(1))},
                raw_text=match.group(0)
            ))
        
        return entities
    
    def _build_parameters(
        self,
        intent: IntentType,
        entities: List[ExtractedEntity],
        text: str
    ) -> Dict[str, Any]:
        """Build action parameters from intent and entities."""
        params = {}
        
        # Get count (from top_n or number)
        for entity in entities:
            if entity.entity_type == "top_n":
                params["count"] = entity.value
                params["sort_by"] = "score"
                params["sort_order"] = "desc"
                break
            elif entity.entity_type == "number" and "count" not in params:
                params["count"] = entity.value
        
        # Get percentage for adjustments
        for entity in entities:
            if entity.entity_type == "percentage":
                # Determine direction from text
                text_lower = text.lower()
                if any(w in text_lower for w in ["increase", "raise", "boost", "up"]):
                    params["adjustment_percent"] = entity.value
                elif any(w in text_lower for w in ["decrease", "lower", "cut", "down"]):
                    params["adjustment_percent"] = -entity.value
                else:
                    params["adjustment_percent"] = entity.value
                break
        
        # Get money amount
        for entity in entities:
            if entity.entity_type == "money":
                params["amount"] = entity.value
                break
        
        # Get scope
        for entity in entities:
            if entity.entity_type == "scope" and entity.value == "all":
                params["scope"] = "all"
                break
        
        # Get ranking filter
        for entity in entities:
            if entity.entity_type == "ranking":
                params["ranking"] = entity.value
                break
        
        # Get comparison filter
        for entity in entities:
            if entity.entity_type == "comparison":
                params["filter"] = entity.value
                break
        
        return params
    
    def _needs_confirmation(self, intent: IntentType, entities: List[ExtractedEntity]) -> bool:
        """Determine if action needs user confirmation."""
        # Always confirm destructive actions
        if intent in [IntentType.DROP_PRODUCT, IntentType.PAUSE]:
            return True
        
        # Confirm bulk actions
        for entity in entities:
            if entity.entity_type == "scope" and entity.value == "all":
                return True
            if entity.entity_type == "top_n" and entity.value > 5:
                return True
        
        # Confirm large adjustments
        for entity in entities:
            if entity.entity_type == "percentage" and abs(entity.value) > 30:
                return True
            if entity.entity_type == "money" and entity.value > 100:
                return True
        
        return False
    
    def _build_suggested_actions(self, parsed: ParsedCommand) -> List[Dict[str, Any]]:
        """Build list of specific actions to execute."""
        actions = []
        
        if not parsed.is_executable:
            return actions
        
        count = parsed.parameters.get("count", 1)
        
        # For deploy, we need to specify which products
        if parsed.action_type == "deploy_product":
            for i in range(count):
                actions.append({
                    "action_type": "deploy_product",
                    "description": f"Deploy product #{i+1} (top by score)",
                    "parameters": {
                        "rank": i + 1,
                        "sort_by": parsed.parameters.get("sort_by", "score"),
                    },
                    "requires_product_id": True  # Need to resolve at execution
                })
        
        # For pause with filter
        elif parsed.action_type == "pause_ad":
            filter_info = parsed.parameters.get("filter", {})
            actions.append({
                "action_type": "pause_ad",
                "description": f"Pause ads matching filter",
                "parameters": {
                    "scope": parsed.parameters.get("scope", "matching"),
                    "filter": filter_info,
                },
                "requires_ad_ids": True
            })
        
        # For budget adjustment
        elif parsed.action_type == "adjust_budget":
            adjustment = parsed.parameters.get("adjustment_percent", 0)
            actions.append({
                "action_type": "adjust_budget",
                "description": f"{'Increase' if adjustment > 0 else 'Decrease'} budget by {abs(adjustment)}%",
                "parameters": {
                    "adjustment_percent": adjustment,
                    "ranking": parsed.parameters.get("ranking"),
                },
                "requires_ad_id": True
            })
        
        return actions
    
    def _check_clarification(self, parsed: ParsedCommand) -> Optional[str]:
        """Check if clarification is needed from the user."""
        
        # Unknown intent
        if parsed.intent == IntentType.UNKNOWN:
            return "I'm not sure what you want to do. Could you rephrase that? For example: 'Deploy the top 3 products' or 'Pause ads under 2% CTR'"
        
        # Deploy without count
        if parsed.action_type == "deploy_product" and "count" not in parsed.parameters:
            return "How many products would you like to deploy? For example: 'Deploy the top 5 products'"
        
        # Pause without filter
        if parsed.action_type == "pause_ad" and "filter" not in parsed.parameters and "scope" not in parsed.parameters:
            return "Which ads should I pause? For example: 'Pause all ads' or 'Pause ads under 2% CTR'"
        
        # Budget adjustment without percentage
        if parsed.action_type == "adjust_budget" and "adjustment_percent" not in parsed.parameters:
            return "By how much should I adjust the budget? For example: 'Increase budget by 20%'"
        
        return None
    
    def get_examples(self) -> List[Dict[str, str]]:
        """Get example commands for each intent."""
        return [
            {
                "command": "Deploy the top 3 products",
                "intent": "deploy",
                "description": "Publishes the 3 highest-scoring products to your store"
            },
            {
                "command": "Pause all ads under 2% CTR",
                "intent": "pause",
                "description": "Pauses all ads with click-through rate below 2%"
            },
            {
                "command": "Increase budget on my best ad by 25%",
                "intent": "adjust_budget",
                "description": "Raises the budget on your top-performing ad by 25%"
            },
            {
                "command": "What's trending in smart home?",
                "intent": "query_trending",
                "description": "Shows current trending products in the smart home niche"
            },
            {
                "command": "How are my ads performing?",
                "intent": "query_performance",
                "description": "Shows performance metrics for your active ads"
            },
            {
                "command": "Drop the worst performing product",
                "intent": "drop_product",
                "description": "Removes the lowest-performing product from your store"
            },
        ]


# Singleton instance
_parser: Optional[NLCommandParser] = None


def get_nl_parser() -> NLCommandParser:
    """Get or create the NL parser singleton."""
    global _parser
    if _parser is None:
        _parser = NLCommandParser()
    return _parser


# === Quick parse function ===

def parse_command(text: str) -> ParsedCommand:
    """
    Quick function to parse a command.
    
    Usage:
        result = parse_command("Deploy the top 5 products")
        if result.is_executable:
            for action in result.suggested_actions:
                execute(action)
    """
    return get_nl_parser().parse(text)

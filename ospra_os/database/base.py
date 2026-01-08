"""
SQLAlchemy Base and Shared Enums for OspraOS Database Models
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
import enum
import json
import os

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class SubscriptionTier(str, enum.Enum):
    """
    User subscription levels - Sky/Flight themed

     Nest → Free tier (grounded, learning)
     Flight → $29/mo (first flight, momentum)
     Soar → $79/mo (high altitude, seeing far)
     Stratosphere → $199/mo (edge of space, first to see)
    """
    NEST = "nest"
    FLIGHT = "flight"
    SOAR = "soar"
    STRATOSPHERE = "stratosphere"

    # Legacy aliases for backward compatibility
    FREE = "nest"        # Maps to NEST
    STARTER = "flight"   # Maps to FLIGHT
    PRO = "soar"         # Maps to SOAR
    ENTERPRISE = "stratosphere"  # Maps to STRATOSPHERE


class Platform(str, enum.Enum):
    """Supported e-commerce platforms"""
    SHOPIFY = "shopify"
    AMAZON = "amazon"
    WOOCOMMERCE = "woocommerce"
    ETSY = "etsy"
    EBAY = "ebay"


class StoreStatus(str, enum.Enum):
    """Store connection and operational status"""
    SETUP = "setup"           # Initial setup in progress
    ACTIVE = "active"         # Connected and operational
    PAUSED = "paused"         # Temporarily paused by user
    DISCONNECTED = "disconnected"  # API connection lost
    ERROR = "error"           # Configuration or API error


class ProductStatus(str, enum.Enum):
    """Product lifecycle status"""
    DISCOVERED = "discovered"      # Found by intelligence engine
    QUEUED = "queued"              # Queued for deployment
    DEPLOYING = "deploying"        # Being deployed
    DEPLOYED = "deployed"          # Successfully deployed
    ACTIVE = "active"              # Live and selling
    PAUSED = "paused"              # Temporarily paused
    DISCONTINUED = "discontinued"  # Removed from store


class DeploymentStatus(str, enum.Enum):
    """Product deployment status per platform"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SYNCING = "syncing"


class AIProvider(str, enum.Enum):
    """AI providers for content generation"""
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    CUSTOM = "custom"


class TaskType(str, enum.Enum):
    """AI task types for cost tracking"""
    PRODUCT_ANALYSIS = "product_analysis"
    CONTENT_GENERATION = "content_generation"
    TITLE_OPTIMIZATION = "title_optimization"
    DESCRIPTION_GENERATION = "description_generation"
    TREND_ANALYSIS = "trend_analysis"
    PRICING_OPTIMIZATION = "pricing_optimization"


class TriggerType(str, enum.Enum):
    """Email automation trigger types"""
    KEYWORD = "keyword"
    SENDER = "sender"
    SUBJECT = "subject"
    LABEL = "label"


class ActionType(str, enum.Enum):
    """Email automation action types"""
    LABEL = "label"
    REPLY = "reply"
    FORWARD = "forward"
    DELETE = "delete"
    MARK_READ = "mark_read"
    AI_REPLY = "ai_reply"  # AI-powered contextual response


class LifecycleStage(str, enum.Enum):
    """Niche lifecycle stages"""
    EMERGING = "emerging"      #  New niche, low competition, growing interest
    GROWTH = "growth"          # [START] Accelerating demand, increasing competition
    PEAK = "peak"              # [TREND] Maximum demand, high competition
    DECLINE = "decline"        # [DECLINE] Decreasing demand, oversaturated
    DEAD = "dead"              #  Minimal demand, avoid


class EntryTiming(str, enum.Enum):
    """Niche entry timing recommendations"""
    EXCELLENT = "excellent"    # Score 80+: Enter immediately
    GOOD = "good"              # Score 60-79: Good time to enter
    FAIR = "fair"              # Score 40-59: Proceed with caution
    POOR = "poor"              # Score 20-39: High risk
    AVOID = "avoid"            # Score <20: Do not enter


class RiskLevel(str, enum.Enum):
    """Risk levels for niche entry"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

"""
OSPRA INTELLIGENCE - OI MEMORY & CONTEXT SYSTEM
Provides persistent memory and universal context for Oi
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from supabase import Client
import json
import hashlib

class OiMemorySystem:
    """
    Three-layer context system for Oi:
    1. Dashboard Context - Real-time data from user's dashboard
    2. User Memory - Persistent, private per-user memory
    3. Universal Knowledge - Shared, anonymized insights
    """
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    # =========================================================================
    # LAYER 1: DASHBOARD CONTEXT (Real-time)
    # =========================================================================
    
    async def get_dashboard_context(self, user_id: str) -> Dict[str, Any]:
        """
        Gather ALL dashboard data for the user.
        This gives Oi full visibility into the user's store.
        """
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "products": [],
            "orders": {"today": 0, "week": 0, "month": 0},
            "revenue": {"today": 0, "week": 0, "month": 0},
            "autopilot": {"is_active": False, "config": {}},
            "pending_actions": [],
            "recent_activity": [],
            "store_health": {}
        }
        
        try:
            # Get user's products
            products_res = self.supabase.table("products").select("*").eq("user_id", user_id).limit(100).execute()
            if products_res.data:
                context["products"] = [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "price": p.get("price"),
                        "supplier_price": p.get("supplier_price"),
                        "profit_margin": p.get("profit_margin"),
                        "score": p.get("oi_score"),
                        "status": p.get("status"),
                        "deployed": p.get("deployed_to_shopify", False)
                    }
                    for p in products_res.data
                ]
            
            # Get autopilot status
            autopilot_res = self.supabase.table("autopilot_config").select("*").eq("user_id", user_id).single().execute()
            if autopilot_res.data:
                context["autopilot"] = {
                    "is_active": autopilot_res.data.get("is_active", False),
                    "config": {
                        "max_daily_actions": autopilot_res.data.get("max_daily_actions", 10),
                        "max_daily_spend": autopilot_res.data.get("max_daily_spend", 100),
                        "auto_deploy": autopilot_res.data.get("auto_deploy_products", False),
                        "confidence_threshold": autopilot_res.data.get("confidence_threshold", 0.8)
                    }
                }
            
            # Get pending actions
            actions_res = self.supabase.table("oi_actions").select("*").eq("user_id", user_id).eq("status", "proposed").limit(20).execute()
            if actions_res.data:
                context["pending_actions"] = [
                    {
                        "id": a.get("id"),
                        "type": a.get("action_type"),
                        "title": a.get("title"),
                        "confidence": a.get("confidence"),
                        "impact": a.get("estimated_impact")
                    }
                    for a in actions_res.data
                ]
            
            # Calculate store health score
            context["store_health"] = self._calculate_store_health(context)
            
        except Exception as e:
            print(f"Error loading dashboard context: {e}")
        
        return context
    
    def _calculate_store_health(self, context: Dict) -> Dict[str, Any]:
        """Calculate overall store health metrics"""
        products = context.get("products", [])
        
        if not products:
            return {"score": 0, "status": "setup_needed", "issues": ["No products added yet"]}
        
        issues = []
        score = 100
        
        # Check product count
        if len(products) < 5:
            issues.append("Low product count - consider adding more products")
            score -= 20
        
        # Check for deployed products
        deployed = sum(1 for p in products if p.get("deployed"))
        if deployed == 0:
            issues.append("No products deployed to Shopify yet")
            score -= 30
        
        # Check autopilot
        if not context.get("autopilot", {}).get("is_active"):
            issues.append("Auto-Pilot is inactive")
            score -= 10
        
        # Check pending actions
        pending = len(context.get("pending_actions", []))
        if pending > 10:
            issues.append(f"{pending} pending actions need attention")
            score -= 15
        
        status = "healthy" if score >= 70 else "needs_attention" if score >= 40 else "critical"
        
        return {
            "score": max(0, score),
            "status": status,
            "issues": issues,
            "product_count": len(products),
            "deployed_count": deployed,
            "pending_actions": pending
        }
    
    # =========================================================================
    # LAYER 2: USER MEMORY (Persistent, Private)
    # =========================================================================
    
    async def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """
        Get persistent memory for a specific user.
        This includes learned preferences, past insights, and conversation context.
        """
        memory = {
            "preferences": {},
            "learned_insights": [],
            "conversation_summary": "",
            "important_facts": [],
            "last_interaction": None
        }
        
        try:
            res = self.supabase.table("oi_user_memory").select("*").eq("user_id", user_id).single().execute()
            if res.data:
                memory = {
                    "preferences": res.data.get("preferences", {}),
                    "learned_insights": res.data.get("learned_insights", []),
                    "conversation_summary": res.data.get("conversation_summary", ""),
                    "important_facts": res.data.get("important_facts", []),
                    "last_interaction": res.data.get("last_interaction")
                }
        except Exception as e:
            # No memory exists yet - that's okay
            pass
        
        return memory
    
    async def update_user_memory(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user's persistent memory.
        Called after conversations to store learned information.
        """
        try:
            # Get existing memory
            existing = await self.get_user_memory(user_id)
            
            # Merge updates
            if "preferences" in updates:
                existing["preferences"].update(updates["preferences"])
            
            if "learned_insight" in updates:
                existing["learned_insights"].append({
                    "insight": updates["learned_insight"],
                    "timestamp": datetime.utcnow().isoformat()
                })
                # Keep only last 50 insights
                existing["learned_insights"] = existing["learned_insights"][-50:]
            
            if "important_fact" in updates:
                if updates["important_fact"] not in existing["important_facts"]:
                    existing["important_facts"].append(updates["important_fact"])
                    # Keep only last 20 facts
                    existing["important_facts"] = existing["important_facts"][-20:]
            
            if "conversation_summary" in updates:
                existing["conversation_summary"] = updates["conversation_summary"]
            
            existing["last_interaction"] = datetime.utcnow().isoformat()
            
            # Upsert to database
            self.supabase.table("oi_user_memory").upsert({
                "user_id": user_id,
                "preferences": existing["preferences"],
                "learned_insights": existing["learned_insights"],
                "conversation_summary": existing["conversation_summary"],
                "important_facts": existing["important_facts"],
                "last_interaction": existing["last_interaction"],
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
            
            return True
        except Exception as e:
            print(f"Error updating user memory: {e}")
            return False
    
    async def save_conversation(self, user_id: str, messages: List[Dict], summary: str = None) -> bool:
        """Save conversation history for context in future chats"""
        try:
            self.supabase.table("oi_conversations").insert({
                "user_id": user_id,
                "messages": messages,
                "summary": summary,
                "message_count": len(messages),
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            print(f"Error saving conversation: {e}")
            return False
    
    async def get_recent_conversations(self, user_id: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation summaries for context"""
        try:
            res = self.supabase.table("oi_conversations").select("summary, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            return []
    
    # =========================================================================
    # LAYER 3: UNIVERSAL KNOWLEDGE (Shared, Anonymized)
    # =========================================================================
    
    async def get_universal_knowledge(self, topic: str = None) -> Dict[str, Any]:
        """
        Get shared knowledge that applies to all users.
        This is anonymized and aggregated - no user-specific data.
        """
        knowledge = {
            "trending_niches": [],
            "best_practices": [],
            "market_insights": [],
            "common_issues": [],
            "success_patterns": []
        }
        
        try:
            # Get trending niches (aggregated from all users, anonymized)
            knowledge["trending_niches"] = await self._get_trending_niches()
            
            # Get best practices
            knowledge["best_practices"] = await self._get_best_practices(topic)
            
            # Get market insights
            knowledge["market_insights"] = await self._get_market_insights()
            
        except Exception as e:
            print(f"Error loading universal knowledge: {e}")
        
        return knowledge
    
    async def _get_trending_niches(self) -> List[Dict]:
        """Get anonymized trending niche data"""
        try:
            res = self.supabase.table("oi_universal_knowledge").select("*").eq("type", "trending_niche").order("score", desc=True).limit(10).execute()
            return [
                {
                    "niche": item.get("title"),
                    "trend": item.get("trend_direction"),
                    "score": item.get("score")
                }
                for item in (res.data or [])
            ]
        except:
            return []
    
    async def _get_best_practices(self, topic: str = None) -> List[Dict]:
        """Get e-commerce best practices"""
        # Static best practices (could be moved to DB)
        practices = [
            {
                "topic": "pricing",
                "practice": "Maintain 30-50% profit margins for sustainable growth",
                "priority": "high"
            },
            {
                "topic": "products",
                "practice": "Focus on products with OI Score above 7 for best results",
                "priority": "high"
            },
            {
                "topic": "ads",
                "practice": "Start with $10-20/day ad spend per product to test performance",
                "priority": "medium"
            },
            {
                "topic": "inventory",
                "practice": "Monitor supplier stock levels to avoid overselling",
                "priority": "high"
            },
            {
                "topic": "trends",
                "practice": "Act on trending products within 2-3 weeks of spike detection",
                "priority": "medium"
            }
        ]
        
        if topic:
            practices = [p for p in practices if topic.lower() in p["topic"].lower()]
        
        return practices
    
    async def _get_market_insights(self) -> List[Dict]:
        """Get current market insights"""
        try:
            res = self.supabase.table("oi_universal_knowledge").select("*").eq("type", "market_insight").order("created_at", desc=True).limit(5).execute()
            return [
                {
                    "insight": item.get("content"),
                    "category": item.get("category"),
                    "date": item.get("created_at")
                }
                for item in (res.data or [])
            ]
        except:
            return []
    
    async def contribute_to_universal(self, insight_type: str, data: Dict, user_id: str) -> bool:
        """
        Contribute anonymized data to universal knowledge.
        User ID is hashed for audit purposes but data is anonymized.
        """
        try:
            # Hash user ID for privacy
            user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
            
            self.supabase.table("oi_universal_knowledge").insert({
                "type": insight_type,
                "title": data.get("title"),
                "content": data.get("content"),
                "category": data.get("category"),
                "score": data.get("score", 0),
                "trend_direction": data.get("trend"),
                "contributor_hash": user_hash,  # Anonymized
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            
            return True
        except Exception as e:
            print(f"Error contributing to universal knowledge: {e}")
            return False
    
    # =========================================================================
    # COMBINED CONTEXT BUILDER
    # =========================================================================
    
    async def build_full_context(self, user_id: str, current_page: str = None, user_query: str = None) -> Dict[str, Any]:
        """
        Build complete context for Oi from all three layers.
        This is what gets sent to Claude for each conversation.
        """
        # Gather all contexts in parallel
        dashboard = await self.get_dashboard_context(user_id)
        memory = await self.get_user_memory(user_id)
        universal = await self.get_universal_knowledge()
        recent_convos = await self.get_recent_conversations(user_id, limit=3)
        
        return {
            "layers": {
                "dashboard": dashboard,
                "memory": memory,
                "universal": universal
            },
            "current_page": current_page,
            "recent_conversations": recent_convos,
            "context_generated_at": datetime.utcnow().isoformat()
        }


# Database migration SQL for reference
MIGRATION_SQL = """
-- User Memory Table (Private, per-user)
CREATE TABLE IF NOT EXISTS oi_user_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    preferences JSONB DEFAULT '{}',
    learned_insights JSONB DEFAULT '[]',
    conversation_summary TEXT,
    important_facts JSONB DEFAULT '[]',
    last_interaction TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation History Table (Private, per-user)
CREATE TABLE IF NOT EXISTS oi_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]',
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Universal Knowledge Table (Shared, anonymized)
CREATE TABLE IF NOT EXISTS oi_universal_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL, -- 'trending_niche', 'market_insight', 'best_practice'
    title VARCHAR(255),
    content TEXT,
    category VARCHAR(100),
    score FLOAT DEFAULT 0,
    trend_direction VARCHAR(20), -- 'up', 'down', 'stable'
    contributor_hash VARCHAR(16), -- Anonymized user reference
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_oi_memory_user ON oi_user_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_oi_convos_user ON oi_conversations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_oi_universal_type ON oi_universal_knowledge(type, score DESC);

-- Row Level Security
ALTER TABLE oi_user_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE oi_conversations ENABLE ROW LEVEL SECURITY;

-- Users can only see their own memory
CREATE POLICY "Users see own memory" ON oi_user_memory
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Users see own conversations" ON oi_conversations
    FOR ALL USING (user_id = auth.uid());

-- Universal knowledge is readable by all authenticated users
ALTER TABLE oi_universal_knowledge ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users read universal" ON oi_universal_knowledge
    FOR SELECT USING (auth.role() = 'authenticated');
"""

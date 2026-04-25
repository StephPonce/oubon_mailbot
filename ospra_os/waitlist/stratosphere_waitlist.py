"""
OSPRA INTELLIGENCE - Stratosphere Waitlist
==========================================
Collect interest for the Stratosphere tier before launch.

Benefits of waitlist:
- Gauge demand before committing resources
- Build anticipation & FOMO
- Get founding member emails for launch
- Create marketing moment when ready
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

FOUNDING_MEMBER_LIMIT = 50  # First 50 get special pricing
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "steph@ospra.io")


# ==================== DATA MODELS ====================

class WaitlistSource(str, Enum):
    PRICING_PAGE = "pricing_page"
    LANDING_PAGE = "landing_page"
    UPGRADE_PROMPT = "upgrade_prompt"  # Shown to Soar users
    REFERRAL = "referral"
    OTHER = "other"


class WaitlistEntry(BaseModel):
    """Stratosphere waitlist signup"""
    email: str
    name: Optional[str] = None
    current_tier: Optional[str] = None  # Are they already a customer?
    user_id: Optional[str] = None  # If logged in
    source: WaitlistSource = WaitlistSource.PRICING_PAGE
    referral_code: Optional[str] = None
    
    # Timestamps
    signed_up_at: datetime = None
    
    # Status
    is_founding_member: bool = False  # First 50
    position: Optional[int] = None  # Waitlist position
    notified: bool = False  # Have we told them it's live?
    converted: bool = False  # Did they actually subscribe?

    # Pydantic v2 serializes datetime as ISO 8601 by default via model_dump_json(),
    # so the old `class Config: json_encoders = {datetime: lambda v: v.isoformat()}`
    # was a no-op in v2 and has been removed.


class WaitlistStats(BaseModel):
    """Waitlist statistics"""
    total_signups: int = 0
    founding_spots_remaining: int = FOUNDING_MEMBER_LIMIT
    from_existing_customers: int = 0  # Soar users interested in upgrading
    from_new_signups: int = 0
    conversion_rate: float = 0.0  # After launch


# ==================== WAITLIST MANAGER ====================

class StratosphereWaitlist:
    """
    Manage the Stratosphere waitlist
    
    For now, stores in memory. TODO: Connect to Supabase.
    """
    
    def __init__(self):
        self._entries: List[WaitlistEntry] = []
        self._emails_set: set = set()  # For quick duplicate check
    
    async def add_to_waitlist(
        self,
        email: str,
        name: Optional[str] = None,
        current_tier: Optional[str] = None,
        user_id: Optional[str] = None,
        source: WaitlistSource = WaitlistSource.PRICING_PAGE,
        referral_code: Optional[str] = None
    ) -> Tuple[WaitlistEntry, bool]:
        """
        Add someone to the Stratosphere waitlist
        
        Returns:
            Tuple of (entry, is_new)
            - is_new = False if they were already on the list
        """
        email_lower = email.lower().strip()
        
        # Check for duplicate
        if email_lower in self._emails_set:
            existing = next((e for e in self._entries if e.email.lower() == email_lower), None)
            logger.info(f"[LIST] Already on waitlist: {email}")
            return existing, False
        
        # Determine position and founding member status
        position = len(self._entries) + 1
        is_founding = position <= FOUNDING_MEMBER_LIMIT
        
        entry = WaitlistEntry(
            email=email_lower,
            name=name,
            current_tier=current_tier,
            user_id=user_id,
            source=source,
            referral_code=referral_code,
            signed_up_at=datetime.now(),
            is_founding_member=is_founding,
            position=position
        )
        
        self._entries.append(entry)
        self._emails_set.add(email_lower)
        
        logger.info(f" Waitlist signup #{position}: {email} {'(Founding Member! [LAUNCH])' if is_founding else ''}")
        
        # TODO: Store in Supabase
        # await self._save_to_database(entry)
        
        return entry, True
    
    def get_stats(self) -> WaitlistStats:
        """Get waitlist statistics"""
        total = len(self._entries)
        from_customers = sum(1 for e in self._entries if e.current_tier and e.current_tier != "nest")
        converted = sum(1 for e in self._entries if e.converted)
        
        return WaitlistStats(
            total_signups=total,
            founding_spots_remaining=max(0, FOUNDING_MEMBER_LIMIT - total),
            from_existing_customers=from_customers,
            from_new_signups=total - from_customers,
            conversion_rate=converted / total if total > 0 else 0.0
        )
    
    def get_all_entries(self) -> List[WaitlistEntry]:
        """Get all waitlist entries (admin only)"""
        return self._entries
    
    def get_founding_members(self) -> List[WaitlistEntry]:
        """Get first 50 founding members"""
        return [e for e in self._entries if e.is_founding_member]
    
    async def check_email(self, email: str) -> Optional[WaitlistEntry]:
        """Check if an email is on the waitlist"""
        email_lower = email.lower().strip()
        return next((e for e in self._entries if e.email.lower() == email_lower), None)


# Global instance
waitlist = StratosphereWaitlist()


# ==================== EMAIL TEMPLATES ====================

def get_waitlist_confirmation_email(entry: WaitlistEntry) -> Dict:
    """
    Confirmation email when someone joins the waitlist
    """
    first_name = entry.name.split()[0] if entry.name else "there"
    
    if entry.is_founding_member:
        subject = f"You're in! Founding Member #{entry.position} "
        founding_section = f"""
        <div style="background: linear-gradient(135deg, #7C3AED 0%, #1E1B4B 100%); border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
            <p style="color: #FFD700; font-size: 14px; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 2px;">Founding Member</p>
            <p style="color: #fff; font-size: 48px; font-weight: bold; margin: 0;">#{entry.position}</p>
            <p style="color: #E0E0FF; margin: 16px 0 0 0;">of 50 spots</p>
        </div>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            <strong>What this means:</strong> When Stratosphere launches, you'll get 
            exclusive founding member pricing locked in forever. You're also first in 
            line for early access.
        </p>
        """
    else:
        subject = f"You're on the list! Position #{entry.position} "
        founding_section = f"""
        <div style="background: #f3f4f6; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
            <p style="color: #666; font-size: 14px; margin: 0 0 8px 0;">Your position</p>
            <p style="color: #1a1a1a; font-size: 48px; font-weight: bold; margin: 0;">#{entry.position}</p>
        </div>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            The first 50 spots for founding member pricing are taken, but you're 
            still on the priority list. We'll notify you as soon as Stratosphere launches.
        </p>
        """
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        
        <p style="font-size: 18px; color: #1a1a1a;">Hey {first_name},</p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            You're officially on the Stratosphere waitlist. [LAUNCH]
        </p>
        
        {founding_section}
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            <strong>What you'll get with Stratosphere:</strong>
        </p>
        
        <ul style="font-size: 15px; color: #444; line-height: 1.8;">
            <li>[START] Day-zero product access (before anyone else sees them)</li>
            <li>[AI] Custom AI trained on YOUR specific niches</li>
            <li> Unlimited e-commerce stores</li>
            <li>[STATS] Predictive saturation alerts</li>
            <li> Dedicated success manager</li>
            <li> Up to 3 team members</li>
        </ul>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            We're putting the finishing touches on the white-glove experience. 
            I'll personally email you when it's ready.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            In the meantime, have you tried <a href="https://app.ospra.io" style="color: #7C3AED;">Ospra Soar</a>? 
            It's our most popular tier and gets you early access to 7-day trending products.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            Talk soon,<br>
            <strong>Steph</strong><br>
            <span style="color: #666;">Founder, Ospra Intelligence</span>
        </p>
        
    </div>
    """
    
    return {
        "to": entry.email,
        "subject": subject,
        "html": html_body,
        "from_name": "Steph from Ospra",
        "from_email": ADMIN_EMAIL,
        "reply_to": ADMIN_EMAIL
    }


def get_waitlist_launch_email(entry: WaitlistEntry) -> Dict:
    """
    Email to send when Stratosphere actually launches
    """
    first_name = entry.name.split()[0] if entry.name else "there"
    
    if entry.is_founding_member:
        subject = " Stratosphere is LIVE — Claim your founding member spot"
        pricing_note = "Your founding member pricing ($149/mo instead of $199/mo) is locked and waiting."
        cta_text = "Claim Founding Member Spot"
    else:
        subject = " Stratosphere is LIVE — You're off the waitlist"
        pricing_note = ""
        cta_text = "Get Stratosphere Access"
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        
        <p style="font-size: 18px; color: #1a1a1a;">Hey {first_name},</p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            The wait is over. <strong>Stratosphere is live.</strong> 
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            {pricing_note}
        </p>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="https://app.ospra.io/upgrade/stratosphere?email={entry.email}" 
               style="background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%); color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">
                {cta_text} →
            </a>
        </div>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            See you in the Stratosphere,<br>
            <strong>Steph</strong>
        </p>
        
    </div>
    """
    
    return {
        "to": entry.email,
        "subject": subject,
        "html": html_body,
        "from_name": "Steph from Ospra",
        "from_email": ADMIN_EMAIL
    }


# ==================== HELPER FUNCTIONS ====================

async def join_waitlist(
    email: str,
    name: Optional[str] = None,
    current_tier: Optional[str] = None,
    user_id: Optional[str] = None,
    source: str = "pricing_page"
) -> Dict:
    """
    Public function to join the waitlist
    
    Returns response suitable for API
    """
    try:
        source_enum = WaitlistSource(source) if source in [s.value for s in WaitlistSource] else WaitlistSource.OTHER
    except ValueError:
        source_enum = WaitlistSource.OTHER
    
    entry, is_new = await waitlist.add_to_waitlist(
        email=email,
        name=name,
        current_tier=current_tier,
        user_id=user_id,
        source=source_enum
    )
    
    stats = waitlist.get_stats()
    
    if is_new:
        # Send confirmation email
        # TODO: await send_email(**get_waitlist_confirmation_email(entry))
        pass
    
    return {
        "success": True,
        "is_new": is_new,
        "position": entry.position,
        "is_founding_member": entry.is_founding_member,
        "founding_spots_remaining": stats.founding_spots_remaining,
        "message": (
            f"[LAUNCH] You're Founding Member #{entry.position}!" 
            if entry.is_founding_member 
            else f"You're #{entry.position} on the waitlist!"
        )
    }

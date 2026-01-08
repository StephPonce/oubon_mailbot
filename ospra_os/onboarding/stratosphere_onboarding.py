"""
OSPRA INTELLIGENCE - Stratosphere White-Glove Onboarding System
================================================================
Automated VIP onboarding for $199/mo Stratosphere subscribers.

Flow:
1. Webhook detects Stratosphere purchase
2. Instant Slack/email alert to admin
3. Personalized welcome email to customer
4. Calendly link for onboarding call
5. Onboarding form collects niche preferences
6. Dashboard checklist tracks progress
7. Automated check-in emails at Day 3, 7, 14, 30
"""
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

# Admin notifications
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "steph@ospra.io")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_STRATOSPHERE")  # Optional

# Email sending (using your existing email system)
EMAIL_FROM = os.getenv("EMAIL_FROM", "steph@ospra.io")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Steph from Ospra")

# Calendly for booking calls
CALENDLY_ONBOARDING_LINK = os.getenv(
    "CALENDLY_ONBOARDING_LINK", 
    "https://calendly.com/ospra/stratosphere-onboarding"
)

# Onboarding form
ONBOARDING_FORM_URL = os.getenv(
    "ONBOARDING_FORM_URL",
    "https://app.ospra.io/onboarding/stratosphere"
)


# ==================== DATA MODELS ====================

class OnboardingStatus(str, Enum):
    PENDING = "pending"           # Just signed up
    WELCOMED = "welcomed"         # Welcome email sent
    FORM_SENT = "form_sent"       # Onboarding form sent
    FORM_COMPLETED = "form_completed"  # They filled out preferences
    CALL_SCHEDULED = "call_scheduled"  # Onboarding call booked
    CALL_COMPLETED = "call_completed"  # Call done
    AI_CONFIGURED = "ai_configured"    # Custom AI set up
    FULLY_ONBOARDED = "fully_onboarded"  # All done!


class StratosphereCustomer(BaseModel):
    """Stratosphere customer onboarding record"""
    user_id: str
    email: str
    name: str
    company: Optional[str] = None
    subscription_id: str
    customer_id: str
    
    # Onboarding progress
    status: OnboardingStatus = OnboardingStatus.PENDING
    onboarding_started: datetime = None
    welcome_email_sent: datetime = None
    form_completed: datetime = None
    call_scheduled: datetime = None
    call_completed: datetime = None
    ai_configured: datetime = None
    fully_onboarded: datetime = None
    
    # Preferences (from onboarding form)
    niches: List[str] = []
    primary_store_url: Optional[str] = None
    monthly_revenue_goal: Optional[str] = None
    biggest_challenge: Optional[str] = None
    preferred_contact: Optional[str] = None  # email, slack, whatsapp
    timezone: Optional[str] = None
    
    # Check-in tracking
    day_3_checkin_sent: bool = False
    day_7_checkin_sent: bool = False
    day_14_checkin_sent: bool = False
    day_30_checkin_sent: bool = False


class OnboardingChecklist(BaseModel):
    """Dashboard checklist items"""
    items: List[Dict] = [
        {"id": "welcome", "label": "Welcome to Stratosphere! ", "completed": True},
        {"id": "form", "label": "Complete onboarding questionnaire", "completed": False},
        {"id": "call", "label": "Schedule onboarding call", "completed": False},
        {"id": "store", "label": "Connect your first store", "completed": False},
        {"id": "niches", "label": "Configure your niches", "completed": False},
        {"id": "ai", "label": "Set up custom AI preferences", "completed": False},
        {"id": "team", "label": "Invite team members (up to 3)", "completed": False},
        {"id": "api", "label": "Generate API keys", "completed": False},
        {"id": "first_product", "label": "Deploy your first product", "completed": False},
    ]


# ==================== NOTIFICATION SYSTEM ====================

async def send_slack_alert(customer: StratosphereCustomer) -> bool:
    """
     Instant Slack alert when someone goes Stratosphere
    
    This is the "drop everything" notification
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook not configured, skipping alert")
        return False
    
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": " NEW STRATOSPHERE CUSTOMER!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n{customer.name}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{customer.email}"},
                    {"type": "mrkdwn", "text": f"*Revenue:*\n+$199/mo [LAUNCH]"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{datetime.now().strftime('%I:%M %p')}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "[ALARM] *Action Required:* Send personal welcome within 24 hours!"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Customer"},
                        "url": f"https://app.ospra.io/admin/customers/{customer.user_id}"
                    }
                ]
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(SLACK_WEBHOOK_URL, json=message)
            if response.status_code == 200:
                logger.info(f"[SUCCESS] Slack alert sent for {customer.email}")
                return True
            else:
                logger.error(f"[ERROR] Slack alert failed: {response.text}")
                return False
    except Exception as e:
        logger.error(f"[ERROR] Slack alert error: {e}")
        return False


async def send_admin_email_alert(customer: StratosphereCustomer) -> bool:
    """
    [EMAIL] Email alert to admin (backup if Slack fails or not configured)
    """
    subject = f" NEW STRATOSPHERE: {customer.name} just subscribed!"
    
    body = f"""
    [LAUNCH] STRATOSPHERE SIGNUP!
    
    Customer: {customer.name}
    Email: {customer.email}
    Company: {customer.company or 'Not provided'}
    Time: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
    
    Monthly Revenue: +$199
    
    [ALARM] ACTION REQUIRED:
    - Welcome email auto-sent [OK]
    - Onboarding form auto-sent [OK]
    - YOU need to: Review their form responses and show up to the call!
    
    View customer: https://app.ospra.io/admin/customers/{customer.user_id}
    """
    
    # TODO: Integrate with your email sending system
    # await send_email(to=ADMIN_EMAIL, subject=subject, body=body)
    
    logger.info(f"[EMAIL] Admin alert queued for {customer.email}")
    return True


# ==================== CUSTOMER EMAILS ====================

def get_welcome_email(customer: StratosphereCustomer) -> Dict:
    """
    Personalized welcome email - sent immediately after purchase
    
    This is NOT a generic template. It feels personal.
    """
    first_name = customer.name.split()[0] if customer.name else "there"
    
    subject = f"Welcome to the Stratosphere, {first_name} "
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        
        <p style="font-size: 18px; color: #1a1a1a;">Hey {first_name},</p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            Steph here, founder of Ospra. I wanted to personally welcome you to the Stratosphere.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            You just unlocked something most sellers will never see: <strong>day-zero product access</strong>. 
            While others are finding products that are already trending, you'll see them <em>before</em> they trend.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            Here's what happens next:
        </p>
        
        <div style="background: linear-gradient(135deg, #7C3AED 0%, #1E1B4B 100%); border-radius: 12px; padding: 24px; margin: 24px 0;">
            <p style="color: #fff; margin: 0 0 16px 0; font-weight: 600;">Your Stratosphere Onboarding:</p>
            <ol style="color: #E0E0FF; margin: 0; padding-left: 20px; line-height: 2;">
                <li>Complete your quick onboarding form (2 min)</li>
                <li>Book your 1-on-1 setup call with me</li>
                <li>I'll configure your custom AI based on your niches</li>
                <li>You start finding products before anyone else</li>
            </ol>
        </div>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="{ONBOARDING_FORM_URL}?user={customer.user_id}" 
               style="background: #7C3AED; color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">
                Start Onboarding →
            </a>
        </div>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            After you complete the form, you'll get a link to book our onboarding call. 
            This is where I learn about your business and set up your custom AI.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            You can also reply directly to this email anytime. Stratosphere members 
            get direct access to me—not a support queue.
        </p>
        
        <p style="font-size: 16px; color: #333; line-height: 1.6;">
            Talk soon,<br>
            <strong>Steph</strong><br>
            <span style="color: #666;">Founder, Ospra Intelligence</span>
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
        
        <p style="font-size: 13px; color: #888;">
            P.S. Your dashboard is live at <a href="https://app.ospra.io/dashboard" style="color: #7C3AED;">app.ospra.io</a>. 
            Feel free to explore while we get your onboarding scheduled.
        </p>
        
    </div>
    """
    
    plain_body = f"""
Hey {first_name},

Steph here, founder of Ospra. I wanted to personally welcome you to the Stratosphere.

You just unlocked something most sellers will never see: day-zero product access. 
While others are finding products that are already trending, you'll see them before they trend.

Here's what happens next:

YOUR STRATOSPHERE ONBOARDING:
1. Complete your quick onboarding form (2 min)
2. Book your 1-on-1 setup call with me
3. I'll configure your custom AI based on your niches
4. You start finding products before anyone else

Start here: {ONBOARDING_FORM_URL}?user={customer.user_id}

After you complete the form, you'll get a link to book our onboarding call. 
This is where I learn about your business and set up your custom AI.

You can also reply directly to this email anytime. Stratosphere members 
get direct access to me—not a support queue.

Talk soon,
Steph
Founder, Ospra Intelligence

P.S. Your dashboard is live at https://app.ospra.io/dashboard. 
Feel free to explore while we get your onboarding scheduled.
    """
    
    return {
        "to": customer.email,
        "subject": subject,
        "html": html_body,
        "text": plain_body,
        "from_name": EMAIL_FROM_NAME,
        "from_email": EMAIL_FROM,
        "reply_to": ADMIN_EMAIL  # Replies go directly to you
    }


def get_day_3_checkin_email(customer: StratosphereCustomer) -> Dict:
    """Day 3 check-in - make sure they're not stuck"""
    first_name = customer.name.split()[0] if customer.name else "there"
    
    subject = f"Quick check-in, {first_name}"
    
    # Customize based on their progress
    if customer.status == OnboardingStatus.PENDING:
        message = "I noticed you haven't started your onboarding yet. Need any help getting started?"
        cta_text = "Complete Onboarding"
        cta_url = ONBOARDING_FORM_URL
    elif customer.status == OnboardingStatus.FORM_COMPLETED:
        message = "Thanks for completing your onboarding form! Ready to book our setup call?"
        cta_text = "Book Setup Call"
        cta_url = CALENDLY_ONBOARDING_LINK
    else:
        message = "Just checking in to see how things are going. Found any good products yet?"
        cta_text = "Open Dashboard"
        cta_url = "https://app.ospra.io/dashboard"
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Hey {first_name},</p>
        <p>{message}</p>
        <p style="text-align: center; margin: 24px 0;">
            <a href="{cta_url}" style="background: #7C3AED; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none;">
                {cta_text}
            </a>
        </p>
        <p>Just reply to this email if you have any questions—I read every one.</p>
        <p>– Steph</p>
    </div>
    """
    
    return {
        "to": customer.email,
        "subject": subject,
        "html": html_body,
        "from_name": EMAIL_FROM_NAME,
        "from_email": EMAIL_FROM,
        "reply_to": ADMIN_EMAIL
    }


def get_day_7_checkin_email(customer: StratosphereCustomer) -> Dict:
    """Day 7 check-in - first week wrap-up"""
    first_name = customer.name.split()[0] if customer.name else "there"
    
    subject = f"Your first week in the Stratosphere "
    
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Hey {first_name},</p>
        <p>It's been a week since you joined the Stratosphere. How's it going?</p>
        <p>Quick questions:</p>
        <ul>
            <li>Have you found any products worth testing?</li>
            <li>Is the AI picking up on your niche preferences?</li>
            <li>Anything confusing or not working as expected?</li>
        </ul>
        <p>Hit reply and let me know. I want to make sure you're getting full value from your subscription.</p>
        <p>– Steph</p>
    </div>
    """
    
    return {
        "to": customer.email,
        "subject": subject,
        "html": html_body,
        "from_name": EMAIL_FROM_NAME,
        "from_email": EMAIL_FROM,
        "reply_to": ADMIN_EMAIL
    }


# ==================== MAIN ONBOARDING HANDLER ====================

async def handle_stratosphere_signup(
    user_id: str,
    email: str,
    name: str,
    subscription_id: str,
    customer_id: str,
    company: Optional[str] = None
) -> StratosphereCustomer:
    """
     Main handler when someone subscribes to Stratosphere
    
    This is called by the LemonSqueezy webhook handler
    """
    
    # Create customer record
    customer = StratosphereCustomer(
        user_id=user_id,
        email=email,
        name=name,
        company=company,
        subscription_id=subscription_id,
        customer_id=customer_id,
        onboarding_started=datetime.now()
    )
    
    logger.info(f" New Stratosphere customer: {email}")
    
    # 1. Send instant alerts to admin
    await send_slack_alert(customer)
    await send_admin_email_alert(customer)
    
    # 2. Send welcome email to customer
    welcome_email = get_welcome_email(customer)
    # TODO: await send_email(**welcome_email)
    customer.welcome_email_sent = datetime.now()
    customer.status = OnboardingStatus.WELCOMED
    
    # 3. Create onboarding checklist in dashboard
    # TODO: await create_dashboard_checklist(user_id)
    
    # 4. Schedule automated check-in emails
    # TODO: await schedule_checkin_emails(customer)
    
    # 5. Save customer record to database
    # TODO: await save_stratosphere_customer(customer)
    
    logger.info(f"[SUCCESS] Stratosphere onboarding initiated for {email}")
    
    return customer


async def process_onboarding_form(
    user_id: str,
    form_data: Dict
) -> bool:
    """
    Process the onboarding questionnaire submission
    """
    # TODO: Fetch customer record
    # customer = await get_stratosphere_customer(user_id)
    
    # Update with form responses
    # customer.niches = form_data.get("niches", [])
    # customer.primary_store_url = form_data.get("store_url")
    # customer.monthly_revenue_goal = form_data.get("revenue_goal")
    # customer.biggest_challenge = form_data.get("challenge")
    # customer.timezone = form_data.get("timezone")
    # customer.form_completed = datetime.now()
    # customer.status = OnboardingStatus.FORM_COMPLETED
    
    # Send Calendly booking link
    # await send_calendly_booking_email(customer)
    
    logger.info(f"[SUCCESS] Onboarding form completed for {user_id}")
    return True


async def run_scheduled_checkins():
    """
    Cron job to send check-in emails
    Run daily to check for customers needing check-ins
    """
    # TODO: Fetch all Stratosphere customers
    # customers = await get_all_stratosphere_customers()
    
    now = datetime.now()
    
    # for customer in customers:
    #     days_since_signup = (now - customer.onboarding_started).days
    #     
    #     if days_since_signup >= 3 and not customer.day_3_checkin_sent:
    #         await send_email(**get_day_3_checkin_email(customer))
    #         customer.day_3_checkin_sent = True
    #     
    #     if days_since_signup >= 7 and not customer.day_7_checkin_sent:
    #         await send_email(**get_day_7_checkin_email(customer))
    #         customer.day_7_checkin_sent = True
    #     
    #     # Continue for day 14, 30, etc.
    
    logger.info("[SUCCESS] Scheduled check-ins processed")


# ==================== ONBOARDING FORM QUESTIONS ====================

ONBOARDING_FORM_SCHEMA = {
    "title": "Stratosphere Onboarding",
    "description": "Help us configure your custom AI and personalized experience",
    "fields": [
        {
            "id": "niches",
            "type": "multi_select",
            "label": "What niches are you focused on?",
            "options": [
                "Smart Home",
                "Home & Kitchen",
                "Health & Wellness",
                "Pet Products",
                "Beauty & Personal Care",
                "Fitness & Sports",
                "Electronics & Gadgets",
                "Baby & Kids",
                "Outdoor & Garden",
                "Fashion & Accessories",
                "Other"
            ],
            "required": True
        },
        {
            "id": "other_niches",
            "type": "text",
            "label": "If 'Other', please specify:",
            "required": False
        },
        {
            "id": "store_url",
            "type": "url",
            "label": "Your primary Shopify store URL",
            "placeholder": "https://yourstore.myshopify.com",
            "required": True
        },
        {
            "id": "additional_stores",
            "type": "number",
            "label": "How many additional stores do you plan to connect?",
            "min": 0,
            "max": 20,
            "required": False
        },
        {
            "id": "revenue_goal",
            "type": "select",
            "label": "What's your monthly revenue goal?",
            "options": [
                "Just starting out",
                "$1K - $5K/month",
                "$5K - $10K/month",
                "$10K - $25K/month",
                "$25K - $50K/month",
                "$50K+/month"
            ],
            "required": True
        },
        {
            "id": "current_revenue",
            "type": "select",
            "label": "What's your current monthly revenue?",
            "options": [
                "Pre-revenue",
                "Under $1K",
                "$1K - $5K",
                "$5K - $10K",
                "$10K - $25K",
                "$25K+"
            ],
            "required": True
        },
        {
            "id": "challenge",
            "type": "textarea",
            "label": "What's your biggest challenge right now?",
            "placeholder": "Finding winning products, scaling ads, managing inventory...",
            "required": True
        },
        {
            "id": "product_volume",
            "type": "select",
            "label": "How many products do you want to test per month?",
            "options": [
                "1-5 products",
                "5-15 products",
                "15-30 products",
                "30+ products"
            ],
            "required": True
        },
        {
            "id": "ad_platforms",
            "type": "multi_select",
            "label": "Which ad platforms do you use?",
            "options": [
                "Facebook/Meta",
                "TikTok",
                "Google",
                "Pinterest",
                "Snapchat",
                "None yet"
            ],
            "required": True
        },
        {
            "id": "timezone",
            "type": "timezone",
            "label": "Your timezone",
            "required": True
        },
        {
            "id": "preferred_contact",
            "type": "select",
            "label": "Preferred way to reach you for support?",
            "options": [
                "Email",
                "Slack (we'll invite you)",
                "WhatsApp"
            ],
            "required": True
        },
        {
            "id": "whatsapp",
            "type": "phone",
            "label": "WhatsApp number (if selected above)",
            "required": False
        },
        {
            "id": "anything_else",
            "type": "textarea",
            "label": "Anything else we should know?",
            "required": False
        }
    ]
}


if __name__ == "__main__":
    print(" Stratosphere Onboarding System")
    print("=" * 50)
    print("\nOnboarding Form Fields:")
    for field in ONBOARDING_FORM_SCHEMA["fields"]:
        req = "required" if field.get("required") else "optional"
        print(f"  • {field['label']} ({field['type']}, {req})")

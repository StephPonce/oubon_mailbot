"""
OSPRA INTELLIGENCE - Onboarding Module
======================================
"""
from .stratosphere_onboarding import (
    StratosphereCustomer,
    OnboardingStatus,
    OnboardingChecklist,
    handle_stratosphere_signup,
    process_onboarding_form,
    send_slack_alert,
    ONBOARDING_FORM_SCHEMA,
    CALENDLY_ONBOARDING_LINK
)

from .routes import router as onboarding_router

__all__ = [
    "StratosphereCustomer",
    "OnboardingStatus", 
    "OnboardingChecklist",
    "handle_stratosphere_signup",
    "process_onboarding_form",
    "send_slack_alert",
    "ONBOARDING_FORM_SCHEMA",
    "CALENDLY_ONBOARDING_LINK",
    "onboarding_router"
]

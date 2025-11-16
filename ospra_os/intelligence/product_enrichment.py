"""Product data enrichment for better AI analysis"""

PRODUCT_ENRICHMENT = {
    "Smart WiFi Light Bulb RGB LED": {
        "description": "Color-changing smart bulb with WiFi connectivity, works with Alexa/Google Home. 16M colors, dimmable, scheduling features. Energy efficient LED technology.",
        "features": [
            "16 million color options with app control",
            "Voice control via Alexa and Google Assistant",
            "Scheduling and automation capabilities",
            "Energy efficient (equivalent to 60W, uses 9W)",
            "No hub required - direct WiFi connection",
            "Group control for multiple bulbs"
        ],
        "use_cases": [
            "Smart home lighting automation",
            "Mood and ambiance lighting",
            "Energy-conscious homeowners",
            "Tech enthusiasts"
        ],
        "target_market": "Tech-savvy homeowners aged 25-45 interested in smart home automation"
    },
    "Smart Door Lock with Fingerprint": {
        "description": "Keyless entry smart lock with fingerprint recognition, app control, and backup keypad. Works with existing deadbolts. Battery powered.",
        "features": [
            "Fingerprint recognition (stores 100+ prints)",
            "Smartphone app control and monitoring",
            "Backup PIN code entry",
            "Activity logs and notifications",
            "Auto-lock feature",
            "Works with existing deadbolt hardware"
        ],
        "use_cases": [
            "Keyless home entry",
            "Rental property management",
            "Family access control",
            "Enhanced home security"
        ],
        "target_market": "Homeowners and property managers seeking convenient security solutions"
    },
    "WiFi Security Camera 1080P": {
        "description": "HD security camera with night vision, motion detection, and cloud storage. Two-way audio, works indoors/outdoors. App-controlled monitoring.",
        "features": [
            "1080P HD video quality",
            "Night vision up to 30ft",
            "Motion detection with alerts",
            "Two-way audio communication",
            "Cloud and local storage options",
            "Weather-resistant (IP65)"
        ],
        "use_cases": [
            "Home security monitoring",
            "Baby/pet monitoring",
            "Package delivery monitoring",
            "Outdoor surveillance"
        ],
        "target_market": "Security-conscious homeowners and renters"
    },
    "Smart Plug with Energy Monitor": {
        "description": "WiFi-enabled smart plug with energy monitoring, scheduling, and voice control. Track power consumption in real-time via app.",
        "features": [
            "Real-time energy monitoring",
            "Voice control (Alexa/Google)",
            "Scheduling and timers",
            "Remote on/off control",
            "Energy usage history and reports",
            "Compact design (no outlet blocking)"
        ],
        "use_cases": [
            "Energy cost tracking",
            "Appliance automation",
            "Vacation mode for lighting",
            "Reduce vampire power drain"
        ],
        "target_market": "Energy-conscious consumers and smart home enthusiasts"
    },
    "Smart Thermostat with Voice Control": {
        "description": "Programmable WiFi thermostat with voice control, learning algorithms, and energy reports. Compatible with most HVAC systems.",
        "features": [
            "Voice control via Alexa/Google",
            "Learning algorithm adapts to schedule",
            "Geofencing auto-adjustment",
            "Energy usage reports and savings tips",
            "Remote control via app",
            "Compatible with 95% of systems"
        ],
        "use_cases": [
            "HVAC cost reduction",
            "Automated climate control",
            "Energy efficiency optimization",
            "Remote temperature management"
        ],
        "target_market": "Cost-conscious homeowners seeking energy savings"
    }
}

def enrich_product(product: dict) -> dict:
    """Add description and features to product"""
    enrichment = PRODUCT_ENRICHMENT.get(product.get("name", ""))

    if enrichment:
        product["description"] = enrichment["description"]
        product["features"] = enrichment["features"]
        product["use_cases"] = enrichment["use_cases"]
        product["target_market"] = enrichment["target_market"]

    return product

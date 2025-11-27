#!/usr/bin/env python3
"""
Automatically create essential Shopify store pages
Creates: About Us, Contact, FAQ, Shipping Info, Returns & Exchanges
"""
import requests
import json
from pathlib import Path

# Read .env file directly
env_file = Path("/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot/.env")
env_vars = {}

with open(env_file, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key] = value

# Shopify credentials
access_token = env_vars.get('SHOPIFY_ADMIN_TOKEN')
store_url = env_vars.get('SHOPIFY_STORE_URL') or env_vars.get('SHOPIFY_STORE')
api_version = env_vars.get('SHOPIFY_API_VERSION', '2025-01')
base_url = f"https://{store_url}/admin/api/{api_version}"

headers = {
    "X-Shopify-Access-Token": access_token,
    "Content-Type": "application/json"
}

print("=" * 70)
print("🚀 AUTOMATED SHOPIFY STORE SETUP")
print("=" * 70)
print()
print(f"Store: {store_url}")
print(f"API Version: {api_version}")
print()

# Page templates
PAGES = [
    {
        "title": "About Us",
        "handle": "about-us",
        "body_html": """
<div class="about-page">
<h1>About Oubon Shop</h1>

<p>Welcome to Oubon Shop, your trusted source for innovative products that make life easier and more enjoyable.</p>

<h2>Our Mission</h2>
<p>We're on a mission to bring you the latest and greatest products from around the world. We carefully curate our selection to ensure you get only the best quality items at competitive prices.</p>

<h2>Why Choose Oubon Shop?</h2>
<ul>
  <li><strong>Carefully Curated Selection</strong> - We test and verify every product before offering it in our store</li>
  <li><strong>Fast & Free Shipping</strong> - Free shipping on orders over $50</li>
  <li><strong>30-Day Returns</strong> - Not satisfied? Return it within 30 days, no questions asked</li>
  <li><strong>Customer-First Service</strong> - Our support team is here to help you 7 days a week</li>
  <li><strong>Secure Shopping</strong> - Your data is protected with industry-standard encryption</li>
</ul>

<h2>Our Story</h2>
<p>Founded with a passion for discovering unique and useful products, Oubon Shop has grown into a destination for smart shoppers who value quality and convenience. We're constantly exploring new products and trends to bring you the best the market has to offer.</p>

<h2>Contact Us</h2>
<p>Questions? We'd love to hear from you!</p>
<p>Email: <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a><br>
Hours: Monday-Friday, 9am-6pm EST</p>

<p>Thank you for choosing Oubon Shop!</p>
</div>
        """,
        "published": True,
        "metafields": [
            {
                "namespace": "seo",
                "key": "title",
                "value": "About Oubon Shop - Smart Shopping, Great Products",
                "type": "single_line_text_field"
            },
            {
                "namespace": "seo",
                "key": "description",
                "value": "Learn about Oubon Shop and our mission to bring you innovative, high-quality products with exceptional customer service.",
                "type": "single_line_text_field"
            }
        ]
    },
    {
        "title": "Contact Us",
        "handle": "contact",
        "body_html": """
<div class="contact-page">
<h1>Contact Oubon Shop</h1>

<p>We're here to help! Whether you have a question about an order, need product recommendations, or just want to say hi, we'd love to hear from you.</p>

<h2>📧 Email Support</h2>
<p><strong>Primary:</strong> <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a><br>
<strong>Orders & Tracking:</strong> <a href="mailto:support@oubonshop.com">support@oubonshop.com</a></p>

<h2>⏰ Business Hours</h2>
<p>Monday - Friday: 9:00 AM - 6:00 PM EST<br>
Saturday: 10:00 AM - 4:00 PM EST<br>
Sunday: Closed</p>

<p><em>We typically respond to emails within 24 hours during business days.</em></p>

<h2>💬 What Can We Help You With?</h2>
<ul>
  <li><strong>Order Questions</strong> - Track your order, modify shipping address, or check order status</li>
  <li><strong>Product Inquiries</strong> - Questions about specific products, availability, or recommendations</li>
  <li><strong>Returns & Exchanges</strong> - Start a return or exchange (see our <a href="/pages/returns-exchanges">Returns Policy</a>)</li>
  <li><strong>Technical Support</strong> - Help with product setup or troubleshooting</li>
  <li><strong>General Questions</strong> - Anything else we can help with!</li>
</ul>

<h2>📦 Before You Contact Us About Orders</h2>
<p>Please have your order number ready (found in your confirmation email). This helps us assist you faster!</p>

<h2>🌐 Store Information</h2>
<p><strong>Website:</strong> <a href="https://oubonshop.com">oubonshop.com</a><br>
<strong>Domain:</strong> Oubon Shop</p>

<h2>📢 Follow Us</h2>
<p>Stay updated on new products, sales, and exclusive offers:</p>
<ul>
  <li>Instagram: @oubonshop (coming soon)</li>
  <li>Facebook: /oubonshop (coming soon)</li>
  <li>TikTok: @oubonshop (coming soon)</li>
</ul>

<p><strong>We look forward to hearing from you!</strong></p>
</div>
        """,
        "published": True
    },
    {
        "title": "Frequently Asked Questions",
        "handle": "faq",
        "body_html": """
<div class="faq-page">
<h1>Frequently Asked Questions</h1>

<p>Find quick answers to common questions about shopping at Oubon Shop.</p>

<h2>📦 Shipping & Delivery</h2>

<h3>How long does shipping take?</h3>
<p><strong>Standard Shipping:</strong> 5-10 business days<br>
<strong>Express Shipping:</strong> 2-4 business days<br>
<strong>Overnight:</strong> 1-2 business days</p>

<h3>Do you offer free shipping?</h3>
<p>Yes! We offer <strong>FREE standard shipping on all orders over $50</strong>. For orders under $50, standard shipping is $5.99.</p>

<h3>Do you ship internationally?</h3>
<p>Yes! We ship to most countries worldwide. International shipping typically takes 10-25 business days. Shipping costs vary by destination and are calculated at checkout.</p>

<h3>How can I track my order?</h3>
<p>Once your order ships, you'll receive a tracking number via email. You can also track your order by logging into your account on our website.</p>

<h2>🔄 Returns & Exchanges</h2>

<h3>What is your return policy?</h3>
<p>We offer a <strong>30-day money-back guarantee</strong>. If you're not completely satisfied, you can return any unused item within 30 days of delivery for a full refund.</p>

<h3>How do I start a return?</h3>
<p>Email us at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> with your order number. We'll send you return instructions within 24 hours.</p>

<h3>Who pays for return shipping?</h3>
<p>For defective or incorrect items, we cover return shipping. For other returns, customers are responsible for return shipping costs.</p>

<h3>Can I exchange an item?</h3>
<p>Absolutely! Contact us at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> to arrange an exchange.</p>

<h2>💳 Payments & Pricing</h2>

<h3>What payment methods do you accept?</h3>
<p>We accept all major credit cards (Visa, Mastercard, American Express, Discover), PayPal, Apple Pay, and Google Pay.</p>

<h3>Is my payment information secure?</h3>
<p>Yes! All transactions are encrypted with industry-standard SSL security. We never store your full credit card information.</p>

<h3>Can I cancel my order?</h3>
<p>If your order hasn't shipped yet, we can cancel it. Contact us immediately at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> with your order number.</p>

<h2>🛍️ Products</h2>

<h3>Are your products authentic?</h3>
<p>Yes! We source all products directly from authorized distributors and manufacturers.</p>

<h3>Do you offer product warranties?</h3>
<p>Many of our products come with manufacturer warranties. Check the product description for specific warranty information.</p>

<h3>Can you help me choose the right product?</h3>
<p>Of course! Email us at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> with your questions, and we'll be happy to help you find the perfect product.</p>

<h2>📧 Contact & Support</h2>

<h3>How can I contact customer support?</h3>
<p>Email: <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a><br>
Hours: Monday-Friday, 9am-6pm EST<br>
Response Time: Within 24 hours</p>

<h3>I have a question that's not answered here</h3>
<p>No problem! Send us an email at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> and we'll get back to you as soon as possible.</p>

<hr>

<p><strong>Still have questions? <a href="/pages/contact">Contact us</a> - we're here to help!</strong></p>
</div>
        """,
        "published": True
    },
    {
        "title": "Shipping Information",
        "handle": "shipping-information",
        "body_html": """
<div class="shipping-page">
<h1>Shipping Information</h1>

<p>Fast, reliable shipping to get your order to you quickly and safely.</p>

<h2>📦 Shipping Methods & Rates</h2>

<table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
  <thead>
    <tr style="background: #f5f5f5;">
      <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Method</th>
      <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Delivery Time</th>
      <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Cost</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding: 12px; border: 1px solid #ddd;"><strong>Standard Shipping</strong></td>
      <td style="padding: 12px; border: 1px solid #ddd;">5-10 business days</td>
      <td style="padding: 12px; border: 1px solid #ddd;"><strong>FREE</strong> (orders $50+) / $5.99 (under $50)</td>
    </tr>
    <tr>
      <td style="padding: 12px; border: 1px solid #ddd;"><strong>Express Shipping</strong></td>
      <td style="padding: 12px; border: 1px solid #ddd;">2-4 business days</td>
      <td style="padding: 12px; border: 1px solid #ddd;">$15.00</td>
    </tr>
    <tr>
      <td style="padding: 12px; border: 1px solid #ddd;"><strong>Overnight Shipping</strong></td>
      <td style="padding: 12px; border: 1px solid #ddd;">1-2 business days</td>
      <td style="padding: 12px; border: 1px solid #ddd;">$25.00</td>
    </tr>
    <tr>
      <td style="padding: 12px; border: 1px solid #ddd;"><strong>International Standard</strong></td>
      <td style="padding: 12px; border: 1px solid #ddd;">10-25 business days</td>
      <td style="padding: 12px; border: 1px solid #ddd;">Varies by destination</td>
    </tr>
  </tbody>
</table>

<h2>⏱️ Processing Time</h2>
<p>Orders are typically processed and shipped within <strong>1-2 business days</strong>. During peak seasons or sales events, processing may take up to 3 business days.</p>

<h2>📍 Tracking Your Order</h2>
<p>Once your order ships, you'll receive:</p>
<ul>
  <li>Email confirmation with tracking number</li>
  <li>Link to track your package in real-time</li>
  <li>Estimated delivery date</li>
</ul>

<p>You can also track your order by:</p>
<ol>
  <li>Logging into your account at oubonshop.com</li>
  <li>Clicking "Order History"</li>
  <li>Selecting your order to view tracking details</li>
</ol>

<h2>🌍 International Shipping</h2>
<p>We ship to most countries worldwide! International shipping includes:</p>
<ul>
  <li><strong>Customs & Duties:</strong> May apply depending on your country (buyer responsible)</li>
  <li><strong>Delivery Time:</strong> 10-25 business days typically</li>
  <li><strong>Tracking:</strong> Full tracking provided for all international orders</li>
  <li><strong>Restrictions:</strong> Some products may have shipping restrictions</li>
</ul>

<h2>📮 PO Boxes & Military Addresses</h2>
<p>Yes! We ship to:</p>
<ul>
  <li>PO Boxes (Standard Shipping only)</li>
  <li>APO/FPO/DPO military addresses</li>
  <li>US Territories (Puerto Rico, Guam, US Virgin Islands, etc.)</li>
</ul>

<h2>❓ Shipping FAQs</h2>

<h3>Can I change my shipping address after ordering?</h3>
<p>If your order hasn't shipped yet, we can update your address. Contact us immediately at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> with your order number.</p>

<h3>What if my package is lost or stolen?</h3>
<p>Contact us at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a>. We'll work with the carrier to locate your package or send a replacement.</p>

<h3>Do you offer weekend delivery?</h3>
<p>Our carriers deliver Monday-Saturday. Sunday delivery is not currently available.</p>

<h2>📧 Questions About Shipping?</h2>
<p>Contact our support team:<br>
Email: <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a><br>
Hours: Monday-Friday, 9am-6pm EST</p>
</div>
        """,
        "published": True
    },
    {
        "title": "Returns & Exchanges",
        "handle": "returns-exchanges",
        "body_html": """
<div class="returns-page">
<h1>Returns & Exchanges</h1>

<p>Not completely satisfied? We've got you covered with our hassle-free 30-day return policy.</p>

<h2>✅ 30-Day Money-Back Guarantee</h2>
<p>We want you to love your purchase! If you're not completely satisfied, return any unused item within <strong>30 days of delivery</strong> for a full refund - no questions asked.</p>

<h2>📋 Return Requirements</h2>
<p>To be eligible for a return, items must be:</p>
<ul>
  <li>✓ Returned within 30 days of delivery</li>
  <li>✓ In unused, like-new condition</li>
  <li>✓ In original packaging (preferred but not required)</li>
  <li>✓ Include all accessories and documentation</li>
</ul>

<h2>🔄 How to Start a Return</h2>
<p>Returns are easy! Just follow these steps:</p>
<ol>
  <li><strong>Contact Us</strong><br>
  Email <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a> with:
    <ul>
      <li>Your order number</li>
      <li>Item(s) you want to return</li>
      <li>Reason for return (optional but helpful)</li>
    </ul>
  </li>
  <li><strong>Get Return Instructions</strong><br>
  We'll email you return shipping instructions within 24 hours</li>
  <li><strong>Ship the Item</strong><br>
  Package the item securely and ship to the address provided</li>
  <li><strong>Receive Your Refund</strong><br>
  Once we receive and inspect the return, we'll process your refund within 5-7 business days</li>
</ol>

<h2>💰 Refund Information</h2>
<ul>
  <li><strong>Refund Method:</strong> Original payment method</li>
  <li><strong>Processing Time:</strong> 5-7 business days after we receive the return</li>
  <li><strong>Amount:</strong> Full purchase price (excluding original shipping if applicable)</li>
  <li><strong>Bank Processing:</strong> May take an additional 3-5 business days to appear in your account</li>
</ul>

<h2>📦 Return Shipping Costs</h2>
<p><strong>Defective or Incorrect Items:</strong> We pay for return shipping<br>
<strong>Change of Mind/Other Reasons:</strong> Customer pays for return shipping</p>

<p><em>Tip: Use a trackable shipping method and save your receipt!</em></p>

<h2>🔁 Exchanges</h2>
<p>Want to exchange for a different item? We're happy to help!</p>
<ol>
  <li>Email us at <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a></li>
  <li>Let us know what you'd like to exchange</li>
  <li>We'll arrange the exchange and send you the new item</li>
</ol>

<h2>⚠️ Non-Returnable Items</h2>
<p>For hygiene and safety reasons, the following items cannot be returned:</p>
<ul>
  <li>Personal care items (if opened)</li>
  <li>Intimate apparel or swimwear (if worn)</li>
  <li>Digital downloads or software</li>
  <li>Gift cards</li>
  <li>Items marked as "final sale"</li>
</ul>

<h2>🛡️ Damaged or Defective Items</h2>
<p>Received a damaged or defective item? We apologize!</p>
<p>Contact us within <strong>7 days of delivery</strong> with:</p>
<ul>
  <li>Order number</li>
  <li>Photos of the damage/defect</li>
  <li>Description of the issue</li>
</ul>

<p>We'll send you a replacement immediately or issue a full refund - your choice!</p>

<h2>📧 Questions About Returns?</h2>
<p>Our customer service team is here to help:<br>
Email: <a href="mailto:hello@oubonshop.com">hello@oubonshop.com</a><br>
Hours: Monday-Friday, 9am-6pm EST<br>
Response Time: Within 24 hours</p>

<hr>

<p><strong>Your satisfaction is our priority. If you have any concerns about your purchase, please don't hesitate to reach out!</strong></p>
</div>
        """,
        "published": True
    }
]

# Create pages
created_pages = []
skipped_pages = []

for page_data in PAGES:
    print(f"Creating page: {page_data['title']}...")

    # Check if page already exists
    check_response = requests.get(
        f"{base_url}/pages.json?handle={page_data['handle']}",
        headers=headers,
        timeout=10
    )

    if check_response.status_code == 200:
        existing = check_response.json().get('pages', [])
        if existing:
            print(f"  ⏭️  Page already exists (ID: {existing[0]['id']})")
            skipped_pages.append(page_data['title'])
            continue

    # Create page
    payload = {"page": page_data}
    response = requests.post(
        f"{base_url}/pages.json",
        headers=headers,
        json=payload,
        timeout=10
    )

    if response.status_code == 201:
        page = response.json().get('page', {})
        print(f"  ✅ Created! (ID: {page['id']}, Handle: {page['handle']})")
        created_pages.append({
            'title': page['title'],
            'id': page['id'],
            'handle': page['handle'],
            'url': f"https://{store_url}/pages/{page['handle']}"
        })
    else:
        print(f"  ❌ Failed: {response.status_code}")
        print(f"     {response.text[:200]}")

print()
print("=" * 70)
print("📊 SETUP SUMMARY")
print("=" * 70)
print()
print(f"✅ Created: {len(created_pages)} pages")
print(f"⏭️  Skipped: {len(skipped_pages)} pages (already exist)")
print()

if created_pages:
    print("📄 NEW PAGES:")
    for page in created_pages:
        print(f"  • {page['title']}")
        print(f"    URL: {page['url']}")
        print()

print("=" * 70)
print("🎯 NEXT STEPS")
print("=" * 70)
print()
print("1. ✅ Pages Created - Review and customize content if needed")
print("2. 📋 Set up Navigation - Add pages to header/footer menus")
print("3. 🔒 Configure Policies - Set up legal policies in Shopify Admin")
print("4. 📦 Add Products - Use Ospra OS discovery system or add manually")
print("5. 🚀 Launch Store - Remove password protection when ready")
print()
print("To view your new pages, visit:")
print(f"  https://{store_url}/pages/about-us")
print(f"  https://{store_url}/pages/contact")
print(f"  https://{store_url}/pages/faq")
print(f"  https://{store_url}/pages/shipping-information")
print(f"  https://{store_url}/pages/returns-exchanges")
print()
print("=" * 70)
print("✨ STORE SETUP COMPLETE!")
print("=" * 70)

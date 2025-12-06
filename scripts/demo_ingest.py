#!/usr/bin/env python
"""Demo script to ingest sample documents for testing."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.voice_bot.config import get_settings
from src.voice_bot.rag.ingest import DocumentIngester


SAMPLE_KNOWLEDGE = """
# Acme Corporation FAQ

## About Us
Acme Corporation is a leading provider of innovative solutions since 1985. 
We specialize in widgets, gadgets, and premium customer service.

## Products

### Widget Pro
Our flagship product, Widget Pro, is designed for enterprise customers.
- Price: $999/year
- Features: Advanced analytics, 24/7 support, custom integrations
- Free trial: 30 days

### Widget Basic
Perfect for small businesses and startups.
- Price: $99/year
- Features: Core functionality, email support, 5 user limit

### Gadget Plus
Our newest addition to the product line.
- Price: $499/year
- Features: IoT integration, real-time monitoring, mobile app

## Support

### Contact Information
- Phone: 1-800-ACME-HELP (1-800-226-3435)
- Email: support@acme-corp.com
- Hours: Monday-Friday, 9 AM - 6 PM EST

### Common Issues

**How do I reset my password?**
Click "Forgot Password" on the login page and follow the instructions sent to your email.

**How do I upgrade my plan?**
Go to Settings > Billing > Upgrade Plan. Changes take effect immediately.

**What payment methods do you accept?**
We accept Visa, MasterCard, American Express, and PayPal.

## Refund Policy
We offer a 30-day money-back guarantee on all products. 
Contact support@acme-corp.com to request a refund.

## Office Locations
- Headquarters: 123 Innovation Way, San Francisco, CA 94102
- East Coast: 456 Tech Avenue, New York, NY 10001
- Europe: 789 Digital Street, London, UK EC1A 1BB
"""


async def main():
    """Ingest sample data for the demo customer."""
    print("🚀 Voice Bot Demo Data Ingestion")
    print("=" * 50)

    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        print("   Make sure you have a .env file with required API keys")
        return

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    customer_id = "demo_acme"
    print(f"\n📝 Ingesting sample knowledge for customer: {customer_id}")

    chunks = await ingester.ingest_text(
        customer_id=customer_id,
        text=SAMPLE_KNOWLEDGE,
        source_name="company_faq.md",
    )

    print(f"✅ Successfully created {chunks} chunks")
    print(f"📁 Vector store saved to: {settings.customer_data_path / customer_id}")

    # Create the customer config file
    import json

    customers_file = settings.customer_data_path / "customers.json"
    customers = {}
    if customers_file.exists():
        with open(customers_file) as f:
            customers = json.load(f)

    customers[customer_id] = {
        "company_name": "Acme Corporation",
        "bot_name": "Alex",
        "personality": "Be warm, helpful, and professional. You're a customer service expert for Acme Corporation.",
        "greeting": "Hello! Welcome to Acme Corporation. I'm Alex, your virtual assistant. How can I help you today?",
        "voice_id": None,
        "created_at": "2024-01-01T00:00:00",
    }

    with open(customers_file, "w") as f:
        json.dump(customers, f, indent=2)

    print(f"✅ Customer config saved to: {customers_file}")
    print("\n🎉 Demo data ready! You can now:")
    print("   1. Start the server: uv run python main.py")
    print("   2. Create a session: POST /api/v1/sessions with customer_id='demo_acme'")


if __name__ == "__main__":
    asyncio.run(main())


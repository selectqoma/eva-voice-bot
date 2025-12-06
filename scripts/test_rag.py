#!/usr/bin/env python
"""Test script to verify RAG retrieval is working."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.voice_bot.config import get_settings
from src.voice_bot.rag.retriever import RAGRetriever


def main():
    """Test RAG retrieval with sample queries."""
    print("🔍 Voice Bot RAG Test")
    print("=" * 50)

    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        print("   Make sure you have a .env file with required API keys")
        return

    retriever = RAGRetriever(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    customer_id = "demo_acme"

    if not retriever.has_knowledge_base(customer_id):
        print(f"❌ No knowledge base found for customer: {customer_id}")
        print("   Run 'python scripts/demo_ingest.py' first")
        return

    print(f"\n✅ Knowledge base found for: {customer_id}")

    # Test queries
    test_queries = [
        "What products do you offer?",
        "How much does Widget Pro cost?",
        "What's your refund policy?",
        "How can I contact support?",
        "Where are your offices located?",
    ]

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 40)

        context = retriever.get_context(customer_id, query, k=2)

        if context:
            # Show first 300 chars of context
            preview = context[:300] + "..." if len(context) > 300 else context
            print(f"📚 Context:\n{preview}")
        else:
            print("❌ No relevant context found")

    print("\n" + "=" * 50)
    print("✅ RAG test complete!")


if __name__ == "__main__":
    main()


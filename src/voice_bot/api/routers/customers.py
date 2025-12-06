"""Customer management API endpoints."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...config import get_settings
from ...models.customer import CustomerConfig, CustomerCreate, CustomerResponse
from ...rag.retriever import RAGRetriever

router = APIRouter()


def _get_customers_file() -> Path:
    """Get the path to the customers JSON file."""
    settings = get_settings()
    return settings.customer_data_path / "customers.json"


def _load_customers() -> dict[str, dict]:
    """Load customers from JSON file."""
    customers_file = _get_customers_file()
    if not customers_file.exists():
        return {}
    with open(customers_file) as f:
        return json.load(f)


def _save_customers(customers: dict[str, dict]) -> None:
    """Save customers to JSON file."""
    customers_file = _get_customers_file()
    customers_file.parent.mkdir(parents=True, exist_ok=True)
    with open(customers_file, "w") as f:
        json.dump(customers, f, indent=2)


@router.get("", response_model=list[CustomerResponse])
async def list_customers():
    """List all customers."""
    settings = get_settings()
    customers = _load_customers()

    retriever = RAGRetriever(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    result = []
    for customer_id, data in customers.items():
        has_kb = retriever.has_knowledge_base(customer_id)
        result.append(
            CustomerResponse(
                customer_id=customer_id,
                company_name=data["company_name"],
                bot_name=data.get("bot_name", "Assistant"),
                personality=data.get("personality", ""),
                greeting=data.get("greeting", ""),
                voice_id=data.get("voice_id"),
                documents_count=1 if has_kb else 0,  # Simplified count
                created_at=data.get("created_at"),
            )
        )

    return result


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(customer: CustomerCreate):
    """Create a new customer."""
    customer_id = str(uuid.uuid4())[:8]  # Short UUID for convenience
    customers = _load_customers()

    customer_data = {
        "company_name": customer.company_name,
        "bot_name": customer.bot_name,
        "personality": customer.personality,
        "greeting": customer.greeting,
        "voice_id": customer.voice_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    customers[customer_id] = customer_data
    _save_customers(customers)

    return CustomerResponse(
        customer_id=customer_id,
        **customer_data,
        documents_count=0,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str):
    """Get a customer by ID."""
    settings = get_settings()
    customers = _load_customers()

    if customer_id not in customers:
        raise HTTPException(status_code=404, detail="Customer not found")

    data = customers[customer_id]

    retriever = RAGRetriever(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )
    has_kb = retriever.has_knowledge_base(customer_id)

    return CustomerResponse(
        customer_id=customer_id,
        company_name=data["company_name"],
        bot_name=data.get("bot_name", "Assistant"),
        personality=data.get("personality", ""),
        greeting=data.get("greeting", ""),
        voice_id=data.get("voice_id"),
        documents_count=1 if has_kb else 0,
        created_at=data.get("created_at"),
    )


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: str, customer: CustomerCreate):
    """Update a customer's configuration."""
    settings = get_settings()
    customers = _load_customers()

    if customer_id not in customers:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_data = {
        "company_name": customer.company_name,
        "bot_name": customer.bot_name,
        "personality": customer.personality,
        "greeting": customer.greeting,
        "voice_id": customer.voice_id,
        "created_at": customers[customer_id].get("created_at"),
    }

    customers[customer_id] = customer_data
    _save_customers(customers)

    retriever = RAGRetriever(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )
    has_kb = retriever.has_knowledge_base(customer_id)

    return CustomerResponse(
        customer_id=customer_id,
        **customer_data,
        documents_count=1 if has_kb else 0,
    )


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: str):
    """Delete a customer and their data."""
    settings = get_settings()
    customers = _load_customers()

    if customer_id not in customers:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Delete customer data
    del customers[customer_id]
    _save_customers(customers)

    # Delete knowledge base if exists
    from ...rag.ingest import DocumentIngester

    ingester = DocumentIngester(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )
    ingester.delete_knowledge_base(customer_id)


@router.get("/{customer_id}/config", response_model=CustomerConfig)
async def get_customer_config(customer_id: str):
    """Get a customer's voice bot configuration."""
    customers = _load_customers()

    if customer_id not in customers:
        raise HTTPException(status_code=404, detail="Customer not found")

    data = customers[customer_id]

    return CustomerConfig(
        customer_id=customer_id,
        company_name=data["company_name"],
        bot_name=data.get("bot_name", "Assistant"),
        personality=data.get("personality", ""),
        greeting=data.get("greeting", ""),
        voice_id=data.get("voice_id"),
    )


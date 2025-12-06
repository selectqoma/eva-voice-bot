"""Customer data models."""

from pydantic import BaseModel, Field


class CustomerConfig(BaseModel):
    """Configuration for a customer's voice bot."""

    customer_id: str = Field(..., description="Unique customer identifier")
    company_name: str = Field(..., description="Customer's company name")
    bot_name: str = Field(default="Assistant", description="Name of the voice bot")
    personality: str = Field(
        default="Be friendly, professional, and concise.",
        description="Bot personality and behavior instructions",
    )
    greeting: str = Field(
        default="Hello! How can I help you today?",
        description="Initial greeting message",
    )
    voice_id: str | None = Field(
        default=None,
        description="Cartesia voice ID (uses default if not specified)",
    )


class CustomerCreate(BaseModel):
    """Request model for creating a new customer."""

    company_name: str = Field(..., min_length=1, max_length=100)
    bot_name: str = Field(default="Assistant", max_length=50)
    personality: str = Field(
        default="Be friendly, professional, and concise.",
        max_length=1000,
    )
    greeting: str = Field(
        default="Hello! How can I help you today?",
        max_length=500,
    )
    voice_id: str | None = None


class CustomerResponse(BaseModel):
    """Response model for customer data."""

    customer_id: str
    company_name: str
    bot_name: str
    personality: str
    greeting: str
    voice_id: str | None
    documents_count: int = 0
    created_at: str | None = None


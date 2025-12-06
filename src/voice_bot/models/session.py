"""Session data models."""

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Request model for creating a new voice session."""

    customer_id: str = Field(..., description="Customer ID to create session for")


class SessionResponse(BaseModel):
    """Response model for a voice session."""

    session_id: str
    customer_id: str
    room_url: str
    token: str
    expires_at: str


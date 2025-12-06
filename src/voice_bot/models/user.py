"""User authentication models."""

from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserBase(BaseModel):
    """Base user model."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


class UserCreate(BaseModel):
    """Request model for user registration."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response model for user data."""
    user_id: str
    email: str
    name: str
    created_at: str | None = None


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class BotConfig(BaseModel):
    """Configuration for a user's voice bot."""
    bot_id: str = Field(..., description="Unique bot identifier")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(default="My Assistant", description="Bot display name")
    
    # Voice settings
    voice_id: str = Field(default="coral", description="Voice ID for TTS")
    voice_speed: str = Field(default="balanced", description="Voice speed setting")
    
    # Identity settings
    bot_persona: str = Field(
        default="You are a helpful, friendly assistant.",
        description="Bot personality and behavior instructions"
    )
    greeting: str = Field(
        default="Hello! How can I help you today?",
        description="Initial greeting message"
    )
    language: str = Field(default="en", description="Primary language")
    
    # Knowledge base
    knowledge_base_enabled: bool = Field(default=False)
    documents: list[str] = Field(default_factory=list)
    
    # Flow configuration
    flow_enabled: bool = Field(default=False)
    flow_config: dict | None = Field(default=None)
    
    # Metadata
    is_active: bool = Field(default=True)
    created_at: str | None = None
    updated_at: str | None = None


class BotCreate(BaseModel):
    """Request model for creating a new bot."""
    name: str = Field(default="My Assistant", max_length=100)
    voice_id: str = Field(default="coral")
    voice_speed: str = Field(default="balanced")
    bot_persona: str = Field(
        default="You are a helpful, friendly assistant.",
        max_length=2000
    )
    greeting: str = Field(
        default="Hello! How can I help you today?",
        max_length=500
    )
    language: str = Field(default="en")
    flow_enabled: bool = Field(default=False)
    flow_config: dict | None = None


class BotUpdate(BaseModel):
    """Request model for updating a bot."""
    name: str | None = None
    voice_id: str | None = None
    voice_speed: str | None = None
    bot_persona: str | None = None
    greeting: str | None = None
    language: str | None = None
    flow_enabled: bool | None = None
    flow_config: dict | None = None
    is_active: bool | None = None


class FlowNode(BaseModel):
    """A node in the conversation flow."""
    id: str
    type: str  # 'start', 'message', 'question', 'condition', 'action', 'end'
    label: str
    content: str | None = None
    position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})
    config: dict = Field(default_factory=dict)


class FlowEdge(BaseModel):
    """An edge connecting flow nodes."""
    id: str
    source: str
    target: str
    label: str | None = None
    condition: str | None = None


class FlowConfig(BaseModel):
    """Complete flow configuration."""
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)


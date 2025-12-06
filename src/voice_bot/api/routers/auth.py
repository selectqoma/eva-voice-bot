"""Authentication API endpoints."""

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Header

from ...config import get_settings
from ...models.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    BotConfig, BotCreate, BotUpdate
)

router = APIRouter()

# Simple secret for token signing (in production, use proper JWT)
# Use a stable secret from environment or a fixed value for development
import os
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "voicebot_dev_secret_key_change_in_production_2024")
TOKEN_EXPIRY_HOURS = 24 * 7  # 7 days


def _get_users_file() -> Path:
    """Get the path to the users JSON file."""
    settings = get_settings()
    return settings.customer_data_path / "users.json"


def _get_bots_file() -> Path:
    """Get the path to the bots JSON file."""
    settings = get_settings()
    return settings.customer_data_path / "bots.json"


def _load_users() -> dict[str, dict]:
    """Load users from JSON file."""
    users_file = _get_users_file()
    if not users_file.exists():
        return {}
    with open(users_file) as f:
        return json.load(f)


def _save_users(users: dict[str, dict]) -> None:
    """Save users to JSON file."""
    users_file = _get_users_file()
    users_file.parent.mkdir(parents=True, exist_ok=True)
    with open(users_file, "w") as f:
        json.dump(users, f, indent=2)


def _load_bots() -> dict[str, dict]:
    """Load bots from JSON file."""
    bots_file = _get_bots_file()
    if not bots_file.exists():
        return {}
    with open(bots_file) as f:
        return json.load(f)


def _save_bots(bots: dict[str, dict]) -> None:
    """Save bots to JSON file."""
    bots_file = _get_bots_file()
    bots_file.parent.mkdir(parents=True, exist_ok=True)
    with open(bots_file, "w") as f:
        json.dump(bots, f, indent=2)


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def _create_token(user_id: str) -> str:
    """Create a simple token."""
    expiry = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    # Use | as separator since : appears in ISO timestamps
    payload = f"{user_id}|{expiry.isoformat()}"
    signature = hmac.new(
        TOKEN_SECRET.encode(), 
        payload.encode(), 
        hashlib.sha256
    ).hexdigest()
    return f"{payload}|{signature}"


def _verify_token(token: str) -> str | None:
    """Verify a token and return user_id if valid."""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            return None
        
        user_id, expiry_str, signature = parts
        payload = f"{user_id}|{expiry_str}"
        
        expected_sig = hmac.new(
            TOKEN_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return None
        
        expiry = datetime.fromisoformat(expiry_str)
        if datetime.utcnow() > expiry:
            return None
        
        return user_id
    except Exception:
        return None


async def get_current_user(authorization: str = Header(None)) -> str:
    """Dependency to get current authenticated user."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth header")
    
    user_id = _verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    users = _load_users()
    if user_id not in users:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user_id


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(user: UserCreate):
    """Register a new user."""
    users = _load_users()
    
    # Check if email already exists
    for uid, data in users.items():
        if data.get("email", "").lower() == user.email.lower():
            raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())[:8]
    user_data = {
        "email": user.email.lower(),
        "name": user.name,
        "password_hash": _hash_password(user.password),
        "created_at": datetime.utcnow().isoformat(),
    }
    
    users[user_id] = user_data
    _save_users(users)
    
    token = _create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            email=user_data["email"],
            name=user_data["name"],
            created_at=user_data["created_at"],
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password."""
    users = _load_users()
    
    # Find user by email
    user_id = None
    user_data = None
    for uid, data in users.items():
        if data.get("email", "").lower() == credentials.email.lower():
            user_id = uid
            user_data = data
            break
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if user_data["password_hash"] != _hash_password(credentials.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = _create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            email=user_data["email"],
            name=user_data["name"],
            created_at=user_data.get("created_at"),
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """Get current user information."""
    users = _load_users()
    user_data = users[user_id]
    
    return UserResponse(
        user_id=user_id,
        email=user_data["email"],
        name=user_data["name"],
        created_at=user_data.get("created_at"),
    )


# Bot management endpoints

@router.get("/bots", response_model=list[BotConfig])
async def list_bots(user_id: str = Depends(get_current_user)):
    """List all bots for the current user."""
    bots = _load_bots()
    user_bots = [
        BotConfig(**bot_data, bot_id=bot_id)
        for bot_id, bot_data in bots.items()
        if bot_data.get("user_id") == user_id
    ]
    return user_bots


@router.post("/bots", response_model=BotConfig, status_code=201)
async def create_bot(bot: BotCreate, user_id: str = Depends(get_current_user)):
    """Create a new bot."""
    bots = _load_bots()
    
    bot_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    
    bot_data = {
        "user_id": user_id,
        "name": bot.name,
        "voice_id": bot.voice_id,
        "voice_speed": bot.voice_speed,
        "bot_persona": bot.bot_persona,
        "greeting": bot.greeting,
        "language": bot.language,
        "knowledge_base_enabled": False,
        "documents": [],
        "flow_enabled": bot.flow_enabled,
        "flow_config": bot.flow_config,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    
    bots[bot_id] = bot_data
    _save_bots(bots)
    
    return BotConfig(**bot_data, bot_id=bot_id)


@router.get("/bots/{bot_id}", response_model=BotConfig)
async def get_bot(bot_id: str, user_id: str = Depends(get_current_user)):
    """Get a specific bot."""
    bots = _load_bots()
    
    if bot_id not in bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_data = bots[bot_id]
    if bot_data.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return BotConfig(**bot_data, bot_id=bot_id)


@router.put("/bots/{bot_id}", response_model=BotConfig)
async def update_bot(bot_id: str, bot: BotUpdate, user_id: str = Depends(get_current_user)):
    """Update a bot's configuration."""
    bots = _load_bots()
    
    if bot_id not in bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot_data = bots[bot_id]
    if bot_data.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update only provided fields
    update_data = bot.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            bot_data[key] = value
    
    bot_data["updated_at"] = datetime.utcnow().isoformat()
    bots[bot_id] = bot_data
    _save_bots(bots)
    
    return BotConfig(**bot_data, bot_id=bot_id)


@router.delete("/bots/{bot_id}", status_code=204)
async def delete_bot(bot_id: str, user_id: str = Depends(get_current_user)):
    """Delete a bot."""
    bots = _load_bots()
    
    if bot_id not in bots:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    if bots[bot_id].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    del bots[bot_id]
    _save_bots(bots)


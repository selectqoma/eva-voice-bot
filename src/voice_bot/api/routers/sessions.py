"""Voice session management API endpoints."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ...agent import AgentConfig, start_agent
from ...agent_realtime import RealtimeAgentConfig, start_realtime_agent
from ...config import get_settings
from ...models.customer import CustomerConfig
from ...models.session import SessionCreate, SessionResponse
from ...rag.retriever import RAGRetriever
from ...services.daily_service import DailyService

router = APIRouter()
logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Voice agent mode."""
    STANDARD = "standard"  # Deepgram STT + GPT-4o-mini + Cartesia TTS
    REALTIME = "realtime"  # OpenAI Realtime API (lower latency)


class RealtimeVoice(str, Enum):
    """OpenAI Realtime API voice options."""
    # Original voices
    ALLOY = "alloy"
    ECHO = "echo"
    SHIMMER = "shimmer"
    # New voices (2024)
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    SAGE = "sage"
    VERSE = "verse"


def _load_customers() -> dict[str, dict]:
    """Load customers from JSON file."""
    settings = get_settings()
    customers_file = settings.customer_data_path / "customers.json"
    if not customers_file.exists():
        return {}
    with open(customers_file) as f:
        return json.load(f)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: SessionCreate,
    background_tasks: BackgroundTasks,
    mode: AgentMode = Query(
        default=AgentMode.REALTIME,
        description="Agent mode: 'realtime' for OpenAI Realtime API (low latency), 'standard' for Deepgram+GPT+Cartesia"
    ),
    voice: RealtimeVoice = Query(
        default=RealtimeVoice.CORAL,
        description="Voice for realtime mode. New voices: ash, ballad, coral, sage, verse. Original: alloy, echo, shimmer"
    ),
):
    """
    Create a new voice session for a customer.

    This will:
    1. Create a Daily.co room
    2. Generate tokens for both the user and the bot
    3. Start the voice agent in the background

    **Agent Modes:**
    - `realtime`: Uses OpenAI Realtime API for ultra-low latency voice-to-voice
    - `standard`: Uses Deepgram (STT) + GPT-4o-mini (LLM) + Cartesia (TTS)

    **Realtime Voices (new):** ash, ballad, coral, sage, verse
    **Realtime Voices (original):** alloy, echo, shimmer

    Returns the room URL and user token for the frontend to connect.
    """
    settings = get_settings()

    # Verify customer exists
    customers = _load_customers()
    if request.customer_id not in customers:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_data = customers[request.customer_id]

    # Create Daily.co room
    daily = DailyService(api_key=settings.daily_api_key)

    try:
        room = await daily.create_room()
        room_url = room["url"]
        room_name = room["name"]
    except Exception as e:
        logger.error(f"Failed to create Daily.co room: {e}")
        raise HTTPException(status_code=500, detail="Failed to create voice room")

    # Create tokens
    try:
        user_token_response = await daily.create_token(room_name, is_owner=False)
        bot_token_response = await daily.create_token(room_name, is_owner=True)
    except Exception as e:
        logger.error(f"Failed to create Daily.co tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session tokens")

    # Prepare customer config
    customer_config = CustomerConfig(
        customer_id=request.customer_id,
        company_name=customer_data["company_name"],
        bot_name=customer_data.get("bot_name", "Assistant"),
        personality=customer_data.get("personality", ""),
        greeting=customer_data.get("greeting", "Hello! How can I help you today?"),
        voice_id=customer_data.get("voice_id"),
    )

    # Prepare RAG retriever
    rag_retriever = RAGRetriever(
        openai_api_key=settings.openai_api_key,
        data_path=settings.customer_data_path,
    )

    # Start the appropriate agent based on mode
    if mode == AgentMode.REALTIME:
        logger.info(f"Starting REALTIME agent for customer {request.customer_id} with voice '{voice.value}'")
        realtime_config = RealtimeAgentConfig(
            openai_api_key=settings.openai_api_key,
            openai_model="gpt-4o-realtime-preview",
            voice=voice.value,
            rag_retriever=rag_retriever,
        )
        background_tasks.add_task(
            start_realtime_agent,
            room_url=room_url,
            token=bot_token_response["token"],
            customer=customer_config,
            agent_config=realtime_config,
            use_rag=True,
        )
    else:
        logger.info(f"Starting STANDARD agent for customer {request.customer_id}")
        agent_config = AgentConfig(
            deepgram_api_key=settings.deepgram_api_key,
            openai_api_key=settings.openai_api_key,
            cartesia_api_key=settings.cartesia_api_key,
            openai_model=settings.openai_model,
            cartesia_voice_id=settings.cartesia_voice_id,
            rag_retriever=rag_retriever,
        )
        background_tasks.add_task(
            start_agent,
            room_url=room_url,
            token=bot_token_response["token"],
            customer=customer_config,
            agent_config=agent_config,
            use_rag=True,
        )

    session_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    return SessionResponse(
        session_id=session_id,
        customer_id=request.customer_id,
        room_url=room_url,
        token=user_token_response["token"],
        expires_at=expires_at,
    )


@router.post("/webhook", include_in_schema=False)
async def daily_webhook(event: dict):
    """
    Handle Daily.co webhooks for session events.

    This can be used to track session analytics, billing, etc.
    """
    event_type = event.get("event")
    logger.info(f"Daily.co webhook: {event_type}")

    # Handle different event types
    if event_type == "room.session.started":
        logger.info(f"Session started in room: {event.get('room')}")
    elif event_type == "room.session.ended":
        logger.info(f"Session ended in room: {event.get('room')}")

    return {"status": "ok"}


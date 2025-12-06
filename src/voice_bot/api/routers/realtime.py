"""Direct browser-to-OpenAI Realtime API endpoints."""

import logging
from enum import Enum

import httpx
from fastapi import APIRouter, HTTPException, Query

from ...config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


class RealtimeVoice(str, Enum):
    """OpenAI Realtime API voice options."""
    ALLOY = "alloy"
    ECHO = "echo"
    SHIMMER = "shimmer"
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    SAGE = "sage"
    VERSE = "verse"


class LatencyMode(str, Enum):
    """Latency optimization mode."""
    LOW = "low"        # Fastest responses, may cut off early
    BALANCED = "balanced"  # Good balance
    QUALITY = "quality"    # Best quality, slower


# Ultra-short system prompt for speed
SYSTEM_INSTRUCTIONS = """You are a fast, helpful voice assistant. Be brief and direct. One sentence answers when possible."""


@router.post("/session")
async def create_realtime_session(
    voice: RealtimeVoice = Query(
        default=RealtimeVoice.CORAL,
        description="Voice for the assistant"
    ),
    latency: LatencyMode = Query(
        default=LatencyMode.LOW,
        description="Latency mode: 'low' for fastest, 'balanced' for normal, 'quality' for best audio"
    ),
):
    """
    Create an ephemeral token for direct browser-to-OpenAI WebRTC connection.
    
    This endpoint returns a short-lived token that the browser can use to
    connect directly to OpenAI's Realtime API via WebRTC.
    
    **Latency Modes:**
    - `low`: Fastest responses (~200ms), responds quickly after you stop talking
    - `balanced`: Normal speed (~400ms), good for conversation
    - `quality`: Best quality (~600ms), waits longer to ensure you're done
    """
    settings = get_settings()
    
    # Latency-optimized settings
    latency_configs = {
        LatencyMode.LOW: {
            "threshold": 0.3,           # More sensitive VAD
            "prefix_padding_ms": 100,   # Less padding
            "silence_duration_ms": 200, # Respond faster after silence
        },
        LatencyMode.BALANCED: {
            "threshold": 0.5,
            "prefix_padding_ms": 200,
            "silence_duration_ms": 400,
        },
        LatencyMode.QUALITY: {
            "threshold": 0.6,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 600,
        },
    }
    
    config = latency_configs[latency]
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-realtime-preview-2024-12-17",
                    "voice": voice.value,
                    "instructions": SYSTEM_INSTRUCTIONS,
                    "input_audio_transcription": None,  # Disable transcription for speed
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": config["threshold"],
                        "prefix_padding_ms": config["prefix_padding_ms"],
                        "silence_duration_ms": config["silence_duration_ms"],
                        "create_response": True,
                        "interrupt_response": True,  # Allow interruptions
                    },
                    "temperature": 0.6,  # Lower = faster, more deterministic
                    "max_response_output_tokens": 150,  # Limit response length
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create realtime session: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to OpenAI API")


"""Realtime/OpenAI endpoints removed."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/session")
async def create_realtime_session():
    """Realtime/OpenAI flow has been removed."""
    raise HTTPException(status_code=410, detail="Realtime/OpenAI flow removed. Use /api/v1/voice/stream instead.")
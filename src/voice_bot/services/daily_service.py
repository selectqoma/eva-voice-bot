"""Daily.co WebRTC service for room management."""

import httpx
import time


class DailyService:
    """Service for managing Daily.co rooms and tokens."""

    BASE_URL = "https://api.daily.co/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def create_room(self, room_name: str | None = None) -> dict:
        """Create a new Daily.co room."""
        async with httpx.AsyncClient() as client:
            # Use time.time() for correct Unix timestamp
            payload = {
                "properties": {
                    "exp": int(time.time()) + 3600,  # 1 hour from now
                    "enable_chat": False,
                    "enable_screenshare": False,
                    "start_video_off": True,
                    "start_audio_off": False,
                }
            }
            if room_name:
                payload["name"] = room_name

            response = await client.post(
                f"{self.BASE_URL}/rooms",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def create_token(
        self,
        room_name: str,
        is_owner: bool = False,
        expires_in_seconds: int = 3600,
    ) -> dict:
        """Create a meeting token for a room."""
        async with httpx.AsyncClient() as client:
            payload = {
                "properties": {
                    "room_name": room_name,
                    "is_owner": is_owner,
                    "exp": int(time.time()) + expires_in_seconds,
                }
            }

            response = await client.post(
                f"{self.BASE_URL}/meeting-tokens",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def delete_room(self, room_name: str) -> None:
        """Delete a Daily.co room."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/rooms/{room_name}",
                headers=self.headers,
            )
            response.raise_for_status()


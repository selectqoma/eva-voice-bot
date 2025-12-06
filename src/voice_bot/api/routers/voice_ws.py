"""WebSocket-based voice pipeline: Deepgram STT → Groq LLM → ElevenLabs TTS.

Optimized for quality and speed.
"""

import asyncio
import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from groq import AsyncGroq
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from elevenlabs import AsyncElevenLabs

from ...config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)

# System prompt for Eva
SYSTEM_PROMPT = """You are Eva, a friendly voice assistant from test-voice-bot. 
Be warm but brief. One short sentence max. No filler words. Direct, helpful answers."""

# Use faster 8B model
GROQ_MODEL = "llama-3.1-8b-instant"

# ElevenLabs voice options
VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",  # Rachel - warm female (default)
    "adam": "pNInz6obpgDQGcFmaJgB",    # Adam - deep male  
    "josh": "TxGEqnHWrfWFTfGW9XjX",    # Josh - young male
    "bella": "EXAVITQu4vr4xnSDxMaL",   # Bella - soft female
    "elli": "MF3mGyEYCl7XYWbV9V6O",    # Elli - young female
    "default": "21m00Tcm4TlvDq8ikWAM",
}


class VoicePipeline:
    """Handles the full voice pipeline: STT → LLM → TTS."""
    
    def __init__(self, websocket: WebSocket, voice: str = "default"):
        self.websocket = websocket
        self.voice = VOICES.get(voice, VOICES["default"])
        self.settings = get_settings()
        self.conversation_history = []
        self.is_processing = False
        self.current_transcript = ""
        
        # Initialize clients
        self.deepgram: Optional[DeepgramClient] = None
        self.groq: Optional[AsyncGroq] = None
        self.elevenlabs: Optional[AsyncElevenLabs] = None
        self.dg_connection = None
        
    async def initialize(self):
        """Initialize all service clients."""
        self.deepgram = DeepgramClient(self.settings.deepgram_api_key)
        self.groq = AsyncGroq(api_key=self.settings.groq_api_key)
        
        if not self.settings.elevenlabs_api_key:
            raise Exception("ElevenLabs API key not configured")
        self.elevenlabs = AsyncElevenLabs(api_key=self.settings.elevenlabs_api_key)
        
        # Set up Deepgram live transcription
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")
        
        # Register event handlers
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        self.dg_connection.on(LiveTranscriptionEvents.Error, self._on_error)
        self.dg_connection.on(LiveTranscriptionEvents.Close, self._on_close)
        
        # Configure Deepgram options
        options = LiveOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            interim_results=True,
            vad_events=True,
            endpointing=300,
        )
        
        # Start the connection
        if await self.dg_connection.start(options):
            logger.info("Deepgram connection started")
            await self._send_greeting()
        else:
            raise Exception("Failed to connect to Deepgram")
    
    async def _send_greeting(self):
        """Send initial greeting when conversation starts."""
        greeting = "Hi, I'm Eva from test-voice-bot. How can I help you?"
        
        try:
            await self.websocket.send_json({"type": "status", "status": "speaking"})
            await self.websocket.send_json({"type": "response", "text": greeting})
            
            self.conversation_history.append({"role": "assistant", "content": greeting})
            
            audio_bytes = await self._generate_tts(greeting)
            await self._send_audio(audio_bytes)
            
            await self.websocket.send_json({"type": "audio_end"})
            await self.websocket.send_json({"type": "status", "status": "listening"})
            
            logger.info("Sent greeting")
        except Exception as e:
            logger.error(f"Error sending greeting: {e}")
    
    async def _on_transcript(self, *args, **kwargs):
        """Handle transcription results from Deepgram."""
        try:
            result = kwargs.get("result")
            if not result:
                return
                
            transcript = result.channel.alternatives[0].transcript
            is_final = result.is_final
            speech_final = getattr(result, 'speech_final', is_final)
            
            if transcript:
                self.current_transcript = transcript
                
                try:
                    await self.websocket.send_json({
                        "type": "transcript",
                        "text": transcript,
                        "is_final": is_final
                    })
                except Exception as e:
                    logger.error(f"Error sending transcript: {e}")
                    return
                
                if speech_final and transcript.strip() and not self.is_processing:
                    await self._process_utterance(transcript)
        except Exception as e:
            logger.error(f"Error in _on_transcript: {e}")
    
    async def _on_error(self, *args, **kwargs):
        """Handle Deepgram errors."""
        error = kwargs.get("error")
        logger.error(f"Deepgram error: {error}")
        try:
            await self.websocket.send_json({"type": "error", "message": f"Transcription error: {error}"})
        except:
            pass
    
    async def _on_close(self, *args, **kwargs):
        """Handle Deepgram connection close."""
        logger.info("Deepgram connection closed, reconnecting...")
        try:
            await self.initialize()
        except Exception as e:
            logger.error(f"Failed to reconnect to Deepgram: {e}")
    
    async def _process_utterance(self, text: str):
        """Process a complete utterance through LLM and TTS."""
        if self.is_processing:
            return
            
        self.is_processing = True
        
        try:
            self.conversation_history.append({"role": "user", "content": text})
            
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            await self.websocket.send_json({"type": "status", "status": "thinking"})
            
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history
            
            response = await self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.5,
                max_tokens=40,
                stream=False,
            )
            
            assistant_text = response.choices[0].message.content.strip()
            self.conversation_history.append({"role": "assistant", "content": assistant_text})
            
            await self.websocket.send_json({"type": "response", "text": assistant_text})
            await self.websocket.send_json({"type": "status", "status": "speaking"})
            
            audio_bytes = await self._generate_tts(assistant_text)
            await self._send_audio(audio_bytes)
            
            logger.info(f"Sent {len(audio_bytes)} bytes of audio")
            
            await self.websocket.send_json({"type": "audio_end"})
            await self.websocket.send_json({"type": "status", "status": "listening"})
            
        except Exception as e:
            logger.error(f"Error processing utterance: {e}")
            await self.websocket.send_json({"type": "error", "message": str(e)})
        finally:
            self.is_processing = False
    
    async def _generate_tts(self, text: str) -> bytes:
        """Generate TTS audio using ElevenLabs."""
        audio_chunks = []
        async for chunk in self.elevenlabs.text_to_speech.convert(
            voice_id=self.voice,
            text=text,
            model_id="eleven_turbo_v2_5",
            output_format="pcm_24000",
            optimize_streaming_latency=3,
        ):
            audio_chunks.append(chunk)
        return b''.join(audio_chunks)
    
    async def _send_audio(self, audio_bytes: bytes):
        """Send audio bytes to the client - send all at once for smoother playback."""
        # Send as one chunk to avoid gaps between chunks
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        await self.websocket.send_json({"type": "audio", "data": audio_b64})
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to Deepgram for transcription."""
        try:
            if self.dg_connection:
                await self.dg_connection.send(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {e}")
    
    async def close(self):
        """Clean up connections."""
        if self.dg_connection:
            await self.dg_connection.finish()
        if self.elevenlabs:
            await self.elevenlabs.close()


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    voice: str = Query(default="default", description="Voice: 'rachel', 'adam', 'josh', 'bella', 'elli'"),
):
    """
    WebSocket endpoint for real-time voice conversation.
    
    Stack: Deepgram STT → Groq LLM → ElevenLabs TTS
    
    Messages from server:
    - {"type": "transcript", "text": "...", "is_final": bool}
    - {"type": "response", "text": "..."}
    - {"type": "audio", "data": "base64..."}
    - {"type": "audio_end"}
    - {"type": "status", "status": "listening|thinking|speaking"}
    - {"type": "error", "message": "..."}
    
    Messages from client:
    - Binary: Raw PCM audio data (16-bit, 16kHz, mono)
    """
    await websocket.accept()
    
    settings = get_settings()
    if not settings.groq_api_key:
        await websocket.send_json({"type": "error", "message": "Groq API key not configured"})
        await websocket.close()
        return
    
    if not settings.elevenlabs_api_key:
        await websocket.send_json({"type": "error", "message": "ElevenLabs API key not configured"})
        await websocket.close()
        return
    
    pipeline = VoicePipeline(websocket, voice=voice)
    
    try:
        await pipeline.initialize()
        await websocket.send_json({"type": "status", "status": "listening"})
        
        async def keep_alive():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
        
        keep_alive_task = asyncio.create_task(keep_alive())
        
        try:
            while True:
                message = await websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    break
                
                if "bytes" in message:
                    await pipeline.send_audio(message["bytes"])
                
                elif "text" in message:
                    data = json.loads(message["text"])
                    if data.get("type") == "config" and "voice" in data:
                        pipeline.voice = VOICES.get(data["voice"], VOICES["default"])
        finally:
            keep_alive_task.cancel()
                        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        await pipeline.close()

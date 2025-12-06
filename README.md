# Eva - Real-time Voice Assistant

A high-quality voice assistant powered by **Deepgram** (STT), **Groq** (LLM), and **ElevenLabs** (TTS). Optimized for natural conversation with premium voice quality.

![Eva Voice Assistant](https://img.shields.io/badge/Voice-ElevenLabs-blueviolet) ![STT](https://img.shields.io/badge/STT-Deepgram-green) ![LLM](https://img.shields.io/badge/LLM-Groq-orange)

## 🎯 Features

- **Real-time voice conversation** via WebSocket
- **Premium voice quality** with ElevenLabs TTS
- **Ultra-fast responses** using Groq's LPU inference
- **Multiple voice options**: Rachel, Adam, Josh, Bella, Elli
- **Simple browser UI** - just click and talk

## 🏗️ Architecture

```
Browser (Mic) → WebSocket → Deepgram STT → Groq LLM → ElevenLabs TTS → Browser (Speaker)
```

| Component | Service | Latency | Cost/min |
|-----------|---------|---------|----------|
| Speech-to-Text | Deepgram Nova-2 | ~200ms | $0.002 |
| LLM | Groq Llama 3.1 8B | ~100ms | ~$0.00001 |
| Text-to-Speech | ElevenLabs Turbo | ~300ms | $0.036 |
| **Total** | | **~600ms** | **~$0.04** |

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/selectqoma/eva-voice-bot.git
cd eva-voice-bot

# Using uv (recommended)
uv sync
```

### 2. Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
DEEPGRAM_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here
```

**Get API Keys:**
- [Deepgram](https://deepgram.com) - Free $200 credits
- [Groq](https://console.groq.com) - Free tier available
- [ElevenLabs](https://elevenlabs.io) - Free tier with 10k chars/month

### 3. Run

```bash
uv run python main.py
```

### 4. Open Browser

Go to **http://localhost:8000** and click "Start Chat" 🎙️

## 🎤 Available Voices

| Voice | Description |
|-------|-------------|
| Rachel | Warm, friendly female (default) |
| Bella | Soft, gentle female |
| Elli | Young, energetic female |
| Adam | Deep, authoritative male |
| Josh | Casual, young male |

## 📁 Project Structure

```
eva-voice-bot/
├── src/voice_bot/
│   ├── api/
│   │   ├── routers/
│   │   │   └── voice_ws.py      # WebSocket voice pipeline
│   │   └── app.py               # FastAPI application
│   ├── static/
│   │   └── cheap.html           # Browser UI
│   └── config.py                # Settings
├── main.py                      # Entry point
├── pyproject.toml               # Dependencies
└── .env.example                 # API key template
```

## ⚙️ Configuration

### System Prompt

Edit the assistant's personality in `src/voice_bot/api/routers/voice_ws.py`:

```python
SYSTEM_PROMPT = """You are Eva, a friendly voice assistant from test-voice-bot. 
Be warm but brief. One short sentence max. No filler words. Direct, helpful answers."""
```

### Greeting

```python
greeting = "Hi, I'm Eva from test-voice-bot. How can I help you?"
```

## 💰 Cost Breakdown

At ~$0.04/minute:
- **1 hour** of conversation = ~$2.40
- **100 hours/month** = ~$240

ElevenLabs is the main cost driver (~90%). Consider their Pro plan ($99/month for 500k chars) for heavy usage.

## 🔧 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Voice assistant UI |
| `WS /api/v1/voice/stream` | WebSocket for voice |
| `GET /docs` | API documentation |

### WebSocket Messages

**From Server:**
```json
{"type": "transcript", "text": "...", "is_final": true}
{"type": "response", "text": "..."}
{"type": "audio", "data": "base64..."}
{"type": "status", "status": "listening|thinking|speaking"}
```

**From Client:**
- Binary: Raw PCM audio (16-bit, 16kHz, mono)

## 🛠️ Development

```bash
# Run with auto-reload
uv run uvicorn src.voice_bot.api.app:create_app --reload --factory

# Check linting
uv run ruff check .
```

## 📝 License

MIT

---

Built with ❤️ using Deepgram, Groq, and ElevenLabs

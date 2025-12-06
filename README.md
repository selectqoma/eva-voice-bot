# Voice Bot - Real-time Voice AI SaaS Platform

A production-ready voice AI platform that enables businesses to deploy custom voice agents with their own knowledge bases. Built with Pipecat for orchestration, Deepgram for STT, GPT-4o-mini for LLM, and Cartesia for ultra-low latency TTS.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Voice Bot Platform                    │
├─────────────────────────────────────────────────────────┤
│  API Layer (FastAPI)                                    │
│  - Customer management                                   │
│  - Document ingestion (RAG)                              │
│  - Session management                                    │
├─────────────────────────────────────────────────────────┤
│  Voice Agent (Pipecat)                                  │
│  - Deepgram STT → GPT-4o-mini (w/ RAG) → Cartesia TTS  │
│  - Daily.co WebRTC transport                            │
│  - Per-customer context injection                        │
├─────────────────────────────────────────────────────────┤
│  RAG Pipeline (LangChain + FAISS)                       │
│  - Document ingestion & chunking                        │
│  - Vector embeddings (OpenAI)                           │
│  - Semantic search & retrieval                          │
└─────────────────────────────────────────────────────────┘
```

## Performance

| Component      | Latency       | Cost              |
|----------------|---------------|-------------------|
| Deepgram STT   | ~200-300ms    | $0.0043/min       |
| GPT-4o-mini    | ~300-500ms    | ~$0.001/turn      |
| Cartesia TTS   | ~75-150ms     | ~$0.01/min        |
| **Total**      | **~600-900ms**| **~$0.02/min**    |

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
```

Required API keys:
- **Deepgram**: Get free $200 credits at [deepgram.com](https://deepgram.com)
- **OpenAI**: Get key at [platform.openai.com](https://platform.openai.com)
- **Cartesia**: Get key at [cartesia.ai](https://cartesia.ai)
- **Daily.co**: Get key at [daily.co](https://daily.co)

### 3. Run the Server

```bash
# Using uv
uv run python main.py

# Or directly
python main.py
```

The API will be available at `http://localhost:8000`.

### 4. API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/customers` | List all customers |
| POST | `/api/v1/customers` | Create a new customer |
| GET | `/api/v1/customers/{id}` | Get customer details |
| PUT | `/api/v1/customers/{id}` | Update customer config |
| DELETE | `/api/v1/customers/{id}` | Delete customer |

### Documents (RAG)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload a document |
| POST | `/api/v1/documents/upload-multiple` | Upload multiple documents |
| POST | `/api/v1/documents/ingest-text` | Ingest raw text |
| DELETE | `/api/v1/documents/{customer_id}` | Delete knowledge base |
| GET | `/api/v1/documents/{customer_id}/status` | Check KB status |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sessions` | Create a voice session |

## Usage Example

### 1. Create a Customer

```bash
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Corp",
    "bot_name": "Alex",
    "personality": "Be warm, helpful, and professional.",
    "greeting": "Hello! Welcome to Acme Corp. How can I help you today?"
  }'
```

### 2. Upload Knowledge Base Documents

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "customer_id=abc123" \
  -F "file=@company_faq.pdf"
```

### 3. Start a Voice Session

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "abc123"}'
```

Response:
```json
{
  "session_id": "...",
  "customer_id": "abc123",
  "room_url": "https://your-domain.daily.co/...",
  "token": "...",
  "expires_at": "..."
}
```

### 4. Connect from Frontend

Use the `room_url` and `token` to connect via Daily.co's JavaScript SDK:

```javascript
import DailyIframe from '@daily-co/daily-js';

const call = DailyIframe.createCallObject();
await call.join({ url: roomUrl, token: token });
```

## Project Structure

```
voice_bot/
├── src/voice_bot/
│   ├── api/
│   │   ├── routers/
│   │   │   ├── customers.py    # Customer management
│   │   │   ├── documents.py    # Document ingestion
│   │   │   └── sessions.py     # Voice session management
│   │   └── app.py              # FastAPI app factory
│   ├── models/
│   │   ├── customer.py         # Customer data models
│   │   └── session.py          # Session data models
│   ├── rag/
│   │   ├── ingest.py           # Document ingestion pipeline
│   │   └── retriever.py        # RAG context retrieval
│   ├── services/
│   │   └── daily_service.py    # Daily.co API client
│   ├── agent.py                # Pipecat voice agent
│   └── config.py               # Settings management
├── customer_data/              # Per-customer vector stores
├── main.py                     # Entry point
├── pyproject.toml              # Dependencies
└── .env.example                # Environment template
```

## Supported Document Types

- PDF (`.pdf`)
- Text files (`.txt`, `.md`)
- Word documents (`.docx`, `.doc`)
- CSV files (`.csv`)

## Customization

### Voice Selection

Cartesia offers multiple voice options. Update the `voice_id` in your customer config or `.env`:

```python
{
  "voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091"  # Sonic voice
}
```

### LLM Model

Switch between OpenAI models in `.env`:

```
OPENAI_MODEL=gpt-4o-mini  # Fast, cost-effective (default)
OPENAI_MODEL=gpt-4o       # More capable, higher latency
```

### RAG Configuration

Adjust chunk size for different use cases in `rag/ingest.py`:

- **Smaller chunks (300-500)**: Better for voice (concise answers)
- **Larger chunks (1000+)**: Better for detailed documents

## Production Considerations

1. **Database**: Replace JSON file storage with PostgreSQL
2. **Vector Store**: Consider Pinecone or Qdrant for scale
3. **Authentication**: Add JWT/OAuth for API security
4. **Rate Limiting**: Implement per-customer rate limits
5. **Monitoring**: Add metrics and logging (e.g., Prometheus, Grafana)
6. **Caching**: Cache vector stores for frequently accessed customers

## License

MIT


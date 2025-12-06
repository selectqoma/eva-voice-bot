"""Voice agent using OpenAI Realtime API for ultra-low latency."""

import asyncio
import logging
from dataclasses import dataclass

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.openai_realtime_beta import (
    OpenAIRealtimeBetaLLMService,
    SessionProperties,
    TurnDetection,
)
from pipecat.transports.services.daily import DailyParams, DailyTransport

from .models.customer import CustomerConfig
from .rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


@dataclass
class RealtimeAgentConfig:
    """Configuration for the OpenAI Realtime voice agent."""

    openai_api_key: str
    openai_model: str = "gpt-4o-realtime-preview"
    voice: str = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
    rag_retriever: RAGRetriever | None = None


class RealtimeVoiceAgent:
    """Ultra-low latency voice agent using OpenAI Realtime API.
    
    This agent uses OpenAI's native voice-to-voice capabilities,
    eliminating the need for separate STT/TTS services.
    """

    def __init__(self, config: RealtimeAgentConfig):
        self.config = config
        self.rag = config.rag_retriever

    def _build_system_prompt(self, customer: CustomerConfig) -> str:
        """Build the system prompt for a customer's bot."""
        return f"""You are {customer.bot_name}, a voice assistant for {customer.company_name}.

{customer.personality}

IMPORTANT GUIDELINES:
- You have access to the company's knowledge base. Use it to answer questions accurately.
- If you don't know something, say so honestly - never make things up.
- Keep responses conversational and brief (1-2 sentences when possible) since this is a voice conversation.
- Speak naturally, as if talking to a friend. Avoid overly formal language.
- If asked about something outside your knowledge base, politely explain you can only help with {customer.company_name}-related topics.

Remember: You are speaking, not writing. Keep it natural and concise.

When you first connect, greet the user with: {customer.greeting}"""

    async def run(
        self,
        room_url: str,
        token: str,
        customer: CustomerConfig,
    ) -> None:
        """
        Run the realtime voice agent.
        
        Args:
            room_url: Daily.co room URL
            token: Daily.co meeting token
            customer: Customer configuration
        """
        logger.info(f"Starting OpenAI Realtime agent for customer {customer.customer_id}")

        # Set up WebRTC transport via Daily.co
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name=customer.bot_name,
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Build system prompt
        system_prompt = self._build_system_prompt(customer)
        
        # Session properties for OpenAI Realtime
        session_properties = SessionProperties(
            modalities=["audio", "text"],
            instructions=system_prompt,
            voice=self.config.voice,
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500,
            ),
            temperature=0.8,
        )

        # OpenAI Realtime API - handles STT, LLM, and TTS in one service
        llm = OpenAIRealtimeBetaLLMService(
            api_key=self.config.openai_api_key,
            model=self.config.openai_model,
            session_properties=session_properties,
        )

        # Build the pipeline - much simpler with Realtime API
        pipeline = Pipeline(
            [
                transport.input(),
                llm,
                transport.output(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        # Handle events
        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            logger.info(f"Participant joined: {participant['id']}")
            # The greeting is in the system prompt, but we can trigger a response
            await llm.send_client_event(
                {
                    "type": "response.create",
                    "response": {
                        "modalities": ["audio", "text"],
                    }
                }
            )

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            logger.info(f"Participant left: {participant['id']}, reason: {reason}")
            await task.queue_frame(EndFrame())

        @transport.event_handler("on_call_state_updated")
        async def on_call_state_updated(transport, state):
            logger.info(f"Call state: {state}")
            if state == "left":
                await task.queue_frame(EndFrame())

        # Run the pipeline
        runner = PipelineRunner()

        try:
            await runner.run(task)
        except Exception as e:
            logger.error(f"Error running realtime voice agent: {e}")
            raise
        finally:
            logger.info(f"Realtime voice agent session ended for {customer.customer_id}")


class RAGRealtimeVoiceAgent(RealtimeVoiceAgent):
    """Realtime voice agent with RAG context injection."""

    def _build_system_prompt_with_context(
        self, customer: CustomerConfig, rag_context: str | None = None
    ) -> str:
        """Build system prompt with optional RAG context."""
        base_prompt = f"""You are {customer.bot_name}, a voice assistant for {customer.company_name}.

{customer.personality}

IMPORTANT GUIDELINES:
- You have access to the company's knowledge base below. Use it to answer questions accurately.
- If you don't know something, say so honestly - never make things up.
- Keep responses conversational and brief (1-2 sentences when possible) since this is a voice conversation.
- Speak naturally, as if talking to a friend. Avoid overly formal language.
- If asked about something outside your knowledge base, politely explain you can only help with {customer.company_name}-related topics.

Remember: You are speaking, not writing. Keep it natural and concise.

When you first connect, greet the user with: {customer.greeting}"""
        
        if rag_context:
            return f"""{base_prompt}

=== COMPANY KNOWLEDGE BASE ===
{rag_context}
=== END KNOWLEDGE BASE ===

Use the information above to answer user questions accurately."""
        
        return base_prompt

    async def run(
        self,
        room_url: str,
        token: str,
        customer: CustomerConfig,
    ) -> None:
        """Run the realtime voice agent with RAG."""
        if not self.rag or not self.rag.has_knowledge_base(customer.customer_id):
            logger.warning(
                f"No knowledge base for customer {customer.customer_id}, running without RAG"
            )
            await super().run(room_url, token, customer)
            return

        logger.info(f"Starting RAG Realtime agent for customer {customer.customer_id}")

        # Pre-fetch comprehensive context from the knowledge base
        initial_context = self.rag.get_context(
            customer.customer_id, 
            "company overview products services pricing support refund policy warranty contact information"
        )

        # Set up transport
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name=customer.bot_name,
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Build system prompt with RAG context
        system_prompt = self._build_system_prompt_with_context(customer, initial_context)

        # Session properties with RAG-enhanced instructions
        session_properties = SessionProperties(
            modalities=["audio", "text"],
            instructions=system_prompt,
            voice=self.config.voice,
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=500,
            ),
            temperature=0.7,
        )

        # OpenAI Realtime API with RAG-enhanced system prompt
        llm = OpenAIRealtimeBetaLLMService(
            api_key=self.config.openai_api_key,
            model=self.config.openai_model,
            session_properties=session_properties,
        )

        # Build simple pipeline
        pipeline = Pipeline(
            [
                transport.input(),
                llm,
                transport.output(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
            ),
        )

        # Event handlers
        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            logger.info(f"Participant joined: {participant['id']}")
            # Trigger initial greeting
            await llm.send_client_event(
                {
                    "type": "response.create",
                    "response": {
                        "modalities": ["audio", "text"],
                    }
                }
            )

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            logger.info(f"Participant left: {participant['id']}")
            await task.queue_frame(EndFrame())

        @transport.event_handler("on_call_state_updated")
        async def on_call_state_updated(transport, state):
            if state == "left":
                await task.queue_frame(EndFrame())

        runner = PipelineRunner()

        try:
            await runner.run(task)
        except Exception as e:
            logger.error(f"Error running RAG realtime voice agent: {e}")
            raise


async def start_realtime_agent(
    room_url: str,
    token: str,
    customer: CustomerConfig,
    agent_config: RealtimeAgentConfig,
    use_rag: bool = True,
) -> None:
    """
    Start a realtime voice agent session.
    
    Args:
        room_url: Daily.co room URL
        token: Daily.co meeting token
        customer: Customer configuration
        agent_config: Agent configuration with API keys
        use_rag: Whether to use RAG for context injection
    """
    if use_rag and agent_config.rag_retriever:
        agent = RAGRealtimeVoiceAgent(agent_config)
    else:
        agent = RealtimeVoiceAgent(agent_config)

    await agent.run(room_url, token, customer)
